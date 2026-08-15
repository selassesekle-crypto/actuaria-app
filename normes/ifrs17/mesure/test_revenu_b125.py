# -*- coding: utf-8 -*-
"""Tests P1 — B125/B126 : identifier n'est pas ajouter.

⚠️ GATE : `py -m unittest discover -s normes -t .`
"""
import unittest

from normes.ifrs17.mesure.lrc_paa import (
    VERDICT_53_ELIGIBLE,
    RefusMesure,
    periode_annuelle,
)
from normes.ifrs17.mesure.revenu_b125 import (
    MOTIF_CHARGE_DISCORDANTE,
    ventiler,
)
from normes.ifrs17.oracles.ica_222092 import ATTENDU_5_2, ENTREE_5_2


def _ventilation_5_2():
    e = ENTREE_5_2
    return ventiler(revenu_periode=ATTENDU_5_2['insurance_revenue'],
                    frais_acquisition=e['frais_acquisition_attribuables'],
                    duree_couverture=e['duree_couverture_ans'])


class T1_LeDoubleCompteEstEmpeche(unittest.TestCase):
    """T1 — le point qui valait 62 097,66 € sur un dossier réel."""

    def test_le_produit_total_n_est_pas_augmente(self):
        """⚠️⚠️ LE VERROU CENTRAL DE CE MODULE.

        B126 : le produit de la periode « doit etre LE MEME QUE » la prime
        affectee a la periode, a deux exceptions LIMITATIVES pres -- les
        composantes d'investissement et l'ajustement du §56. Le recouvrement
        des frais d'acquisition n'en fait pas partie : la prime affectee
        contient DEJA le chargement d'acquisition. L'ajouter le compterait
        deux fois.
        """
        v = _ventilation_5_2()
        self.assertEqual(v.total, ATTENDU_5_2['insurance_revenue'])
        self.assertEqual(v.total, 500.0)
        # ce qu'aurait donne l'addition, et qu'on refuse
        self.assertNotEqual(v.total, 500.0 + v.recouvrement)
        print(f"    OK P1 : produit {v.total:.0f}, inchange. L'addition "
              f"aurait donne {500.0 + v.recouvrement:.0f}")

    def test_la_ventilation_somme_au_total(self):
        v = _ventilation_5_2()
        self.assertAlmostEqual(v.recouvrement + v.service, v.total, 6)
        self.assertAlmostEqual(v.recouvrement, 100.0, 6)
        self.assertAlmostEqual(v.service, 400.0, 6)
        print(f"    OK P1b : {v.recouvrement:.0f} de recouvrement + "
              f"{v.service:.0f} de service = {v.total:.0f}")

    def test_la_charge_egale_le_produit_de_recouvrement(self):
        """B125 : « Elle doit comptabiliser LE MEME MONTANT a titre de
        charges afferentes aux activites d'assurance. »"""
        v = _ventilation_5_2()
        self.assertEqual(v.charge_egale, v.recouvrement)
        print(f"    OK P1c : charge {v.charge_egale:.0f} = produit de "
              f"recouvrement {v.recouvrement:.0f}, comme B125 l'impose")

    def test_la_charge_B125_est_deja_dans_les_charges_de_service(self):
        """⚠️ LE RACCORD AVEC §55, ET IL EMPECHE UN SECOND DOUBLE COMPTE.

        L'amortissement des frais d'acquisition figure DEJA dans
        `charges_service` (100 sur l'exemple 5.2, avec 50 de maintenance).
        La charge de B125 est CETTE charge-la, pas une charge de plus. Les
        additionner porterait les charges a 250 au lieu de 150.
        """
        e = ENTREE_5_2
        p = periode_annuelle(
            primes_attendues=e['prime'],
            duree_couverture=e['duree_couverture_ans'],
            frais_acquisition_attribuables=e['frais_acquisition_attribuables'],
            frais_maintenance_attribuables=(
                e['frais_maintenance_attribuables_an1']),
            frais_non_attribuables=0.0,
            verdict_53_declare=VERDICT_53_ELIGIBLE)
        v = _ventilation_5_2()
        self.assertEqual(p.charges_service,
                         ATTENDU_5_2['insurance_service_expenses'])
        self.assertLess(v.charge_egale, p.charges_service)
        self.assertAlmostEqual(
            p.charges_service - v.charge_egale,
            e['frais_maintenance_attribuables_an1'], 6)
        print(f"    OK P1d : charges {p.charges_service:.0f} = "
              f"{v.charge_egale:.0f} (B125) + "
              f"{e['frais_maintenance_attribuables_an1']:.0f} (maintenance) "
              f"— jamais 250")


class T2_CeQueCeModuleNePeutPasEtablir(unittest.TestCase):
    """T2 — la base d'affectation est une lecture, pas un oracle."""

    def test_la_base_d_affectation_est_declaree_comme_une_lecture(self):
        """⚠️ B125 IMPOSE UNE MANIERE « SYSTEMATIQUE QUI REFLETE
        L'ECOULEMENT DU TEMPS ». Le prorata lineaire en est une, et c'est
        celle de l'exemple ICA -- mais une entite peut en retenir une autre,
        tout aussi systematique. Le module applique le lineaire et le DIT.
        """
        v = _ventilation_5_2()
        self.assertIn('systématique', v.base)
        self.assertIn('pas la seule', v.base.replace('pas \n', 'pas '))
        print(f"    OK P2 : base declaree — {v.base[:46]}...")

    def test_l_oracle_ne_publie_pas_cette_ventilation(self):
        """⚠️⚠️ CE QUI EST CONFRONTE ET CE QUI NE L'EST PAS.

        L'exemple ICA 5.2 publie un produit de 500 et des charges de 150. Il
        NE PUBLIE PAS << dont 100 au titre du recouvrement >>. La regle du
        non-double-compte est donc confrontee a l'oracle -- le total doit
        rester 500 -- mais la VENTILATION ne l'est pas. Ce test existe pour
        qu'on ne lise jamais ce fichier vert comme une validation de la
        repartition par l'ICA.
        """
        self.assertNotIn('recouvrement', ' '.join(ATTENDU_5_2))
        self.assertEqual(set(ATTENDU_5_2), {
            'insurance_revenue', 'insurance_service_expenses',
            'insurance_service_result', 'autres_charges', 'resultat', 'lrc'})
        print("    OK P2b : l'oracle ne porte AUCUNE ventilation B125 — le "
              "total est atteste, la repartition est une lecture")


class T3_LesRefus(unittest.TestCase):
    """T3 — une part plus grande que le tout n'est pas une part."""

    def test_un_recouvrement_superieur_au_produit_est_refuse(self):
        with self.assertRaises(RefusMesure) as ctx:
            ventiler(revenu_periode=100.0, frais_acquisition=500.0,
                     duree_couverture=1)
        self.assertEqual(ctx.exception.motif, MOTIF_CHARGE_DISCORDANTE)
        self.assertIn("À L'INTÉRIEUR", str(ctx.exception))
        print("    OK P3 : part > tout -> refus motive, jamais un service "
              "negatif rendu en silence")

    def test_une_duree_invalide_est_refusee(self):
        for duree in (0, -2):
            with self.assertRaises(RefusMesure):
                ventiler(revenu_periode=500.0, frais_acquisition=200.0,
                         duree_couverture=duree)
        print("    OK P3b : duree <= 0 refusee")


if __name__ == '__main__':
    unittest.main()
