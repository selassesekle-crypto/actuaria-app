# -*- coding: utf-8 -*-
"""Tests O1 — la SOURCE se tient-elle debout, et se présente-t-elle bien ?

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️⚠️ CE QUE CE FICHIER NE TESTE PAS : LA PLATEFORME. Aucune ligne ici
n'appelle un calcul du dépôt — la mesure PAA n'est pas encore bâtie. Ces
tests établissent deux choses, et deux seulement :

  1. que les valeurs de la source BOUCLENT entre elles, donc que je les ai
     transcrites sans en perdre ni en inventer ;
  2. qu'aucune valeur ne peut être lue sans son autorité et ses lacunes.

⚠️ NE JAMAIS PRÉSENTER CE FICHIER VERT COMME UNE VALIDATION IFRS 17 DE LA
PLATEFORME. Ce serait exactement le piège que ce dépôt traque : un
instrument qui rend « OK » sans avoir rien mesuré de ce qu'on croit. La
confrontation viendra quand la mesure existera, et c'est là qu'on la verra
d'abord rouge.
"""
import unittest

from normes.ifrs17.oracles.ica_222092 import (
    ATTENDU_5_2,
    AUTORITE,
    CHAINE_EXACTE_5_6_1,
    DEVISE,
    ENTREE_5_2,
    ENTREE_5_6_1,
    HYPOTHESES_5_2,
    HYPOTHESES_5_6_1,
    LACUNES,
    PORTEE_REELLE_5_6_1,
    ROLL_FORWARD_5_6_1,
    SOURCE,
    TOLERANCE,
)


class T1_LaSourceSePresente(unittest.TestCase):
    """T1 — une valeur sans son autorité sera crue normative dans six mois."""

    def test_la_citation_porte_l_auteur_et_le_document(self):
        for morceau in ('222092', '2022', 'Canadian Institute of Actuaries'):
            self.assertIn(morceau, SOURCE)
        # ⚠️ ET LA DEVISE EST ABSTRAITE. Ces montants ne sont pas des euros :
        # les additionner a un portefeuille reel serait une faute silencieuse,
        # puisque les ordres de grandeur se ressemblent.
        self.assertEqual(DEVISE, 'CU')
        self.assertNotIn(DEVISE, ('EUR', '€', 'USD'))
        print(f"    OK T1 : citation complete, {len(SOURCE)} caracteres, "
              f"devise abstraite « {DEVISE} »")

    def test_l_autorite_dit_que_la_source_n_est_pas_contraignante(self):
        """⚠️ LE POINT QUI PROTEGE UN DOSSIER DEVANT UN CAC. Une note
        educative d'un institut national n'est ni la norme, ni un exemple
        illustratif de l'IASB. Le dire ici evite qu'on l'invoque comme tel.
        """
        self.assertIn('NON CONTRAIGNANTE', AUTORITE)
        self.assertIn('IASB', AUTORITE)
        self.assertIn('synthétique', AUTORITE)
        print("    OK T1b : l'autorite est bornee des deux cotes — sous "
              "l'IASB, au-dessus d'un jeu synthetique")

    def test_les_lacunes_sont_enumerees_pas_resumees(self):
        """Une lacune tue vaut un faux verrou : on croirait couvert ce qui
        ne l'est pas."""
        self.assertGreaterEqual(len(LACUNES), 6)
        joint = ' '.join(LACUNES)
        for manque in ('déficitaire', 'LIC', '§57', 'acquisition'):
            self.assertIn(manque, joint)
        print(f"    OK T1c : {len(LACUNES)} lacunes nommees, dont le groupe "
              "deficitaire et le LIC")

    def test_les_hypotheses_accompagnent_les_valeurs(self):
        """⚠️ UNE VALEUR ATTENDUE SANS SES HYPOTHESES NE VEUT RIEN DIRE.

        500 de revenue n'est juste QUE sous prorata temporis ; 400 de LRC
        QUE si les frais d'acquisition sont capitalises et amortis, l'option
        §59 a) n'etant pas retenue ; le roll-forward de 5.6.1 QUE si la
        composante de financement est jugee significative. Changer une
        hypothese change la reponse — les taire ferait passer un oracle pour
        universel quand il est conditionnel.
        """
        self.assertEqual(HYPOTHESES_5_2['actualisation'], 'aucune')
        self.assertFalse(HYPOTHESES_5_2['groupe_deficitaire'])
        self.assertIn('§59 a)', HYPOTHESES_5_2['frais_acquisition'])
        self.assertIn('prorata', HYPOTHESES_5_2['base_affectation'])
        self.assertIn('§56', HYPOTHESES_5_6_1['composante_financement'])
        self.assertFalse(HYPOTHESES_5_6_1['groupe_deficitaire'])
        print(f"    OK T1d : {len(HYPOTHESES_5_2)} hypotheses pour 5.2, "
              f"{len(HYPOTHESES_5_6_1)} pour 5.6.1, toutes ecrites")

    def test_la_tolerance_est_celle_qui_a_ete_mesuree(self):
        """⚠️ 0,5 ET NON 1. La source conseille 1 unite ; sur un solde de
        1 040 cela vaut 0,1 %, assez lache pour laisser passer un defaut.
        L'ecart reel maximum mesure est 0,40."""
        self.assertEqual(TOLERANCE, 0.5)
        ecart_max = max(
            abs(p[c] - e[c])
            for p, e in zip(ROLL_FORWARD_5_6_1[1:], CHAINE_EXACTE_5_6_1)
            for c in ('charge_financiere', 'lrc_cloture'))
        self.assertLess(ecart_max, TOLERANCE)
        print(f"    OK T1d : tolerance {TOLERANCE}, ecart publie/exact "
              f"maximum mesure {ecart_max:.2f}")


class T2_LaSection5_2Boucle(unittest.TestCase):
    """T2 — les six postes de 5.2 se déduisent-ils des entrées ?"""

    def test_les_six_postes_se_recalculent_depuis_les_entrees(self):
        e, a = ENTREE_5_2, ATTENDU_5_2
        revenue = e['prime'] / e['duree_couverture_ans']
        amorti = e['frais_acquisition_attribuables'] / e['duree_couverture_ans']
        charges = e['frais_maintenance_attribuables_an1'] + amorti
        autres = (e['frais_acquisition_non_attribuables']
                  + e['frais_maintenance_non_attribuables_par_an'])
        self.assertEqual(revenue, a['insurance_revenue'])
        self.assertEqual(charges, a['insurance_service_expenses'])
        self.assertEqual(revenue - charges, a['insurance_service_result'])
        self.assertEqual(autres, a['autres_charges'])
        self.assertEqual(a['insurance_service_result'] - autres, a['resultat'])
        print("    OK T2 : les 6 postes de 5.2 se recalculent exactement")

    def test_le_LRC_diminue_des_frais_d_acquisition_non_amortis(self):
        """⚠️ LE POSTE QUI PORTE TOUTE LA VALEUR DE CET EXEMPLE.

        Le LRC vaut 400, pas 500. Les frais d'acquisition non amortis
        viennent EN DIMINUTION du LRC ; ils ne forment pas un actif separe.
        Une implementation qui les logerait dans une ligne d'actif distincte
        afficherait 500, avec un bilan qui equilibre quand meme. C'est cette
        erreur-la, invisible autrement, que l'exemple attrape.
        """
        e, a = ENTREE_5_2, ATTENDU_5_2
        non_amortis = (e['frais_acquisition_attribuables']
                       / e['duree_couverture_ans'])
        encaisse_non_acquis = e['prime'] - a['insurance_revenue']
        self.assertEqual(encaisse_non_acquis - non_amortis, a['lrc'])
        self.assertNotEqual(a['lrc'], encaisse_non_acquis)
        print(f"    OK T2b : LRC {a['lrc']:.0f} = {encaisse_non_acquis:.0f} "
              f"- {non_amortis:.0f}, et NON {encaisse_non_acquis:.0f}")


class T3_LaSection5_6_1Boucle(unittest.TestCase):
    """T3 — le roll-forward publié, et l'unité d'écart de l'année 2."""

    def test_le_roll_forward_publie_boucle_dans_la_tolerance(self):
        ecarts = []
        for p in ROLL_FORWARD_5_6_1[1:]:
            calc = (p['lrc_ouverture'] + p['charge_financiere']
                    + p['revenu_total'])
            ecarts.append(calc - p['lrc_cloture'])
            self.assertLessEqual(abs(ecarts[-1]), 1.0, p['arrete'])
        self.assertEqual([abs(x) for x in ecarts], [0.0, 1.0, 0.0])
        print(f"    OK T3 : bouclage publie, ecarts {[abs(x) for x in ecarts]}"
              " — exact aux annees 1 et 3, 1 unite a l'annee 2")

    def test_les_composantes_du_revenu_somment_au_total(self):
        for p in ROLL_FORWARD_5_6_1[1:]:
            self.assertEqual(p['revenu_financement'] + p['revenu_prime'],
                             p['revenu_total'], p['arrete'])
        print("    OK T3b : financement + prime = total, aux 3 arretes")

    def test_la_chaine_non_arrondie_explique_l_unite_d_ecart(self):
        """⚠️⚠️ CECI N'EST PAS UNE VALIDATION EXTERNE. On applique les
        formules DECLAREES par la source a ses propres entrees : c'est une
        verification de COHERENCE INTERNE, pas une confrontation. Elle
        etablit une seule chose — que l'unite d'ecart de l'annee 2 vient de
        l'arrondi de presentation, et pas d'une valeur fausse.
        """
        lrc = ENTREE_5_6_1['prime']
        taux, duree = ENTREE_5_6_1['taux_verrouille'], 3
        cumul_charges = cumul_revenu = 0.0
        for an, exact in enumerate(CHAINE_EXACTE_5_6_1, start=1):
            charge = lrc * taux
            cumul_charges += charge
            revenu_fin = (cumul_charges - cumul_revenu) / (duree - an + 1)
            cumul_revenu += revenu_fin
            lrc = lrc + charge - revenu_fin - ENTREE_5_6_1['prime'] / duree
            self.assertAlmostEqual(charge, exact['charge_financiere'], 3)
            self.assertAlmostEqual(lrc, exact['lrc_cloture'], 3)
        self.assertAlmostEqual(lrc, 0.0, 9)
        print("    OK T3c : la chaine NON ARRONDIE boucle exactement aux 3 "
              "arretes — l'ecart publie est un arrondi, rien d'autre")

    def test_la_portee_reelle_est_ecrite_et_ne_flatte_pas(self):
        """⚠️ LE ZERO DE L'ANNEE 3 NE PROUVE PRESQUE RIEN : le LRC DOIT
        s'eteindre en fin de couverture. Un calcul faux qui n'aurait perdu
        aucun terme y arriverait aussi."""
        self.assertIn('forcé', PORTEE_REELLE_5_6_1)
        self.assertIn('arrondi', PORTEE_REELLE_5_6_1)
        self.assertEqual(ROLL_FORWARD_5_6_1[-1]['lrc_cloture'], 0.0)
        print("    OK T3d : la portee reelle de l'oracle est ecrite — le "
              "zero final est structurel, pas une observation")


class T4_LesDeuxConventionsDeSigne(unittest.TestCase):
    """T4 — le même document publie le revenu dans les deux sens."""

    def test_5_2_publie_positif_et_5_6_1_publie_negatif(self):
        """⚠️ LE PIEGE POUR UN BANC D'ESSAI. Quelle que soit la convention
        que la plateforme retiendra, l'un des deux oracles devra etre
        retourne — et ce retournement doit etre DECLARE au point de
        comparaison, jamais silencieux."""
        self.assertGreater(ATTENDU_5_2['insurance_revenue'], 0)
        for p in ROLL_FORWARD_5_6_1[1:]:
            self.assertLess(p['revenu_total'], 0)
        print("    OK T4 : 5.2 publie le revenu positif, 5.6.1 negatif — "
              "meme document, conventions opposees")


if __name__ == '__main__':
    unittest.main()
