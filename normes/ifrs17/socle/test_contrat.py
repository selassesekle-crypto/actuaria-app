# -*- coding: utf-8 -*-
"""Tests D1 — le vocabulaire de l'objet contrat et la fonction de capacités.

⚠️ CES TESTS NE VIVENT PAS DANS LA GATE `direction_non_vie`. Le paquet
`normes` a la sienne :
    py -m unittest discover -s normes -t .
C'est la mitigation posée avec le lot : au lot R1, un fichier de test placé
là où aucune gate ne le voyait avait fait découvrir 56 modules au lieu de 57
sans que rien ne le signale. On ne le refait pas.
"""
import unittest

from normes.ifrs17.socle.contrat import (
    CHAMPS, COUVERTURE_INDETERMINEE, EXIGENCES, NIVEAUX, NIVEAU_SOCLE,
    capacites, champs_bloquants, champs_du_niveau, champs_scelles,
    exigences_hors_portee, reference)

#: Les quatre colonnes qu'on ira demander à un assureur.
MINIMAL = ('portefeuille', 'date_emission', 'prime', 'fin_couverture')

#: Ce que ces quatre colonnes doivent débloquer, et rien d'autre.
MINIMAL_DEBLOQUE = {
    'portefeuilles', 'cohortes_annuelles', 'eligibilite_paa_verifiee',
    'lrc', 'revenu',
}


class T1_VocabulaireCoherent(unittest.TestCase):
    """T1 — le catalogue ne se contredit pas lui-même."""

    def test_exigences_ne_citent_que_des_champs_connus(self):
        """Toute exigence se fonde sur des champs qui existent."""
        for nom, ex in EXIGENCES.items():
            for groupe in ex.requiert:
                inconnus = groupe - set(CHAMPS)
                self.assertFalse(
                    inconnus,
                    f"{nom} exige des champs absents du catalogue : {inconnus}")
        print(f"    OK T1 : {len(EXIGENCES)} exigences, "
              f"{len(CHAMPS)} champs, aucune référence morte")

    def test_aucune_exigence_inatteignable(self):
        """Avec tous les champs, toutes les exigences sont atteignables.

        Une exigence qu'aucune combinaison ne débloque serait un catalogue qui
        promet ce qu'il ne tient pas.
        """
        toutes = capacites(set(CHAMPS))
        mortes = sorted(n for n, ok in toutes.items() if not ok)
        self.assertEqual(mortes, [], f"exigences inatteignables : {mortes}")
        print(f"    OK T1b : les {len(toutes)} exigences sont atteignables")

    def test_niveaux_partitionnent_les_champs(self):
        """Chaque champ appartient à un niveau, et les niveaux couvrent tout."""
        vus = set()
        for niv in NIVEAUX:
            vus |= set(champs_du_niveau(niv))
        self.assertEqual(vus, set(CHAMPS))
        with self.assertRaises(KeyError):
            champs_du_niveau('INEXISTANT')
        print(f"    OK T1c : {len(NIVEAUX)} niveaux couvrent les "
              f"{len(CHAMPS)} champs")


class T2_QuatreColonnesMinimales(unittest.TestCase):
    """T2 — ce qu'un client obtient avec le fichier minimal."""

    def test_les_quatre_colonnes_debloquent_exactement_cinq_exigences(self):
        """C'est la promesse qu'on ira faire à un assureur."""
        cap = capacites(MINIMAL)
        obtenu = {n for n, ok in cap.items() if ok}
        self.assertEqual(obtenu, MINIMAL_DEBLOQUE)
        print(f"    OK T2 : {len(MINIMAL)} colonnes -> "
              f"{len(obtenu)} exigences sur {len(EXIGENCES)} | "
              + ', '.join(reference(n).split(' — ')[0] for n in sorted(obtenu)))

    def test_ce_qui_reste_hors_portee_nomme_le_champ_manquant(self):
        """Le diagnostic doit dire le COÛT d'une absence, pas la taire."""
        hors = exigences_hors_portee(MINIMAL)
        self.assertEqual(set(hors), set(EXIGENCES) - MINIMAL_DEBLOQUE)
        self.assertIn('frais_acquisition',
                      hors['frais_acquisition_dans_lrc'])
        self.assertIn('sinistres_attendus', hors['classement_16a_calcule'])
        print(f"    OK T2b : {len(hors)} exigences hors de portee, "
              f"chacune avec le champ qui manque")


class T3_FraisAcquisition(unittest.TestCase):
    """T3 — l'effet mesuré du champ le plus absent du dépôt."""

    def test_les_frais_debloquent_trois_exigences_de_plus(self):
        """§55 a) ii), B125 et §59 a) — aucune autre."""
        sans = {n for n, ok in capacites(MINIMAL).items() if ok}
        avec = {n for n, ok in
                capacites(MINIMAL + ('frais_acquisition',)).items() if ok}
        self.assertEqual(avec - sans, {
            'frais_acquisition_dans_lrc',
            'amortissement_frais_acquisition',
            'option_charges_acquisition'})
        self.assertEqual(sans - avec, set())
        print(f"    OK T3 : frais_acquisition -> {len(sans)} puis "
              f"{len(avec)} exigences (+3)")

    def test_les_frais_seuls_ne_suffisent_pas(self):
        """B125 et §59 a) exigent aussi les bornes de couverture."""
        cap = capacites(('portefeuille', 'date_emission', 'frais_acquisition'))
        self.assertTrue(cap['frais_acquisition_dans_lrc'])
        self.assertFalse(cap['amortissement_frais_acquisition'])
        self.assertFalse(cap['option_charges_acquisition'])
        print("    OK T3b : sans bornes de couverture, B125 et 59a) "
              "restent hors de portee")


class T4_RefusEtScellement(unittest.TestCase):
    """T4 — ce qui fait refuser, et ce qui ne se corrige plus après."""

    def test_les_champs_bloquants_sont_au_socle(self):
        """On ne refuse que sur des champs du socle."""
        for c in champs_bloquants():
            self.assertIn(c, CHAMPS)
            self.assertEqual(CHAMPS[c].niveau, NIVEAU_SOCLE)
        self.assertEqual(champs_bloquants(), ('date_emission', 'portefeuille'))
        print(f"    OK T4 : refus sur {', '.join(champs_bloquants())}")

    def test_les_champs_scelles_sont_ceux_de_l_unite_de_compte(self):
        """§16, §22 et §53 s'apprecient a la creation du groupe."""
        self.assertEqual(
            champs_scelles(),
            ('classe_profitabilite', 'date_emission', 'portefeuille'))
        print(f"    OK T4b : {len(champs_scelles())} champs scelles, "
              "a confirmer avant tout registre")


class T5_Generalite(unittest.TestCase):
    """T5 — l'objet n'est pas taille pour le seul non-vie."""

    def test_duree_indeterminee_distincte_d_une_absence(self):
        """« Sans terme prevu » et « on ne sait pas » ne se confondent pas.

        Une couverture indeterminee est une donnee PRESENTE : elle tranche
        §53 b) — negativement, puisqu'elle excede un an. Une absence laisse
        la question ouverte. Les deux ne debloquent donc pas la meme chose.
        """
        self.assertIsNotNone(COUVERTURE_INDETERMINEE)
        self.assertNotEqual(COUVERTURE_INDETERMINEE, '')
        avec = capacites(('portefeuille', 'date_emission', 'fin_couverture'))
        sans = capacites(('portefeuille', 'date_emission'))
        self.assertTrue(avec['eligibilite_paa_verifiee'])
        self.assertFalse(sans['eligibilite_paa_verifiee'])
        print("    OK T5 : couverture indeterminee representable et "
              "distincte d'une absence")

    def test_ce_qui_est_hors_perimetre_est_nommable(self):
        """VFA et composante d'investissement : refusables, pas silencieux."""
        cap = capacites(('participation_directe', 'composante_investissement'))
        self.assertTrue(cap['signalement_participation_directe'])
        self.assertTrue(cap['signalement_composante_investissement'])
        print("    OK T5b : §45/B101-B118 et §85 signalables")

    def test_aucun_champ_ne_suppose_une_couverture_annuelle(self):
        """Aucun champ ne code « annuel » : la duree est une donnee."""
        for nom in CHAMPS:
            self.assertNotIn('annuel', nom)
            self.assertNotIn('un_an', nom)
        print("    OK T5c : aucun champ ne prejuge de la duree")


class T6_ContratDeSurface(unittest.TestCase):
    """T6 — les fonctions publiques se comportent comme annoncé."""

    def test_champs_inconnus_ignores(self):
        """Un client a le droit d'avoir des colonnes qui ne nous regardent pas."""
        self.assertEqual(capacites(MINIMAL),
                         capacites(MINIMAL + ('CODE_AGENCE', 'ZONE')))
        print("    OK T6 : colonnes etrangeres ignorees en silence")

    def test_reference_cite_le_paragraphe(self):
        """Un livrable doit pouvoir citer, pas paraphraser."""
        self.assertTrue(reference('cohortes_annuelles').startswith(
            'IFRS 17 §22, §25 — '))
        with self.assertRaises(KeyError):
            reference('exigence_qui_n_existe_pas')
        print("    OK T6b : reference() cite le paragraphe et leve sur "
              "une cle inconnue")


if __name__ == '__main__':
    unittest.main(verbosity=2)
