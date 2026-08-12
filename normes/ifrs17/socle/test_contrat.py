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
    CHAMPS,
    COUVERTURE_INDETERMINEE,
    EXIGENCES,
    NIVEAU_SOCLE,
    NIVEAUX,
    SOURCE_IFRS17,
    SOURCE_INVARIANT,
    SOURCES_ADMISES,
    capacites,
    champs_bloquants,
    champs_du_niveau,
    champs_scelles,
    exigences_hors_norme,
    exigences_hors_portee,
    reference,
)

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


class T1bis_Provenance(unittest.TestCase):
    """T1-bis — chaque exigence déclare si elle vient de la norme.

    ⚠️ CE VERROU EXISTE PARCE QUE L'ERREUR A ÉTÉ COMMISE ICI. La règle
    d'invariance de devise citait le §30, qui régit la CONVERSION selon
    IAS 21 — l'inverse de ce qu'elle posait. Le paragraphe existait ; il ne
    disait pas ce qu'on lui prêtait. Aucun test ne distingue une citation
    exacte d'une citation hors sujet — seule la relecture du texte le fait.
    Ce que ces tests garantissent, c'est plus modeste et c'est tout ce qui
    est mécanisable : rien ne passe pour une obligation de la norme sans
    l'avoir déclaré.
    """

    def test_vocabulaire_de_source_ferme(self):
        """Aucune source hors du vocabulaire contrôlé."""
        for nom, ex in EXIGENCES.items():
            self.assertIn(ex.source, SOURCES_ADMISES,
                          f"{nom} porte une source inconnue : {ex.source}")
        print(f"    OK T1bis : {len(EXIGENCES)} exigences, sources dans "
              f"{{{', '.join(SOURCES_ADMISES)}}}")

    def test_une_exigence_ne_vient_pas_de_la_norme_et_le_dit(self):
        """L'invariance de devise est une règle produit, pas IFRS 17."""
        hors = exigences_hors_norme()
        self.assertEqual(set(hors), {'devise_entite_invariante'})
        self.assertEqual(hors['devise_entite_invariante'].source,
                         SOURCE_INVARIANT)
        print(f"    OK T1bis-b : {len(hors)} exigence sur {len(EXIGENCES)} "
              f"ne vient pas de la norme, et le declare")

    def test_les_exigences_de_la_norme_citent_un_paragraphe(self):
        """Une référence IFRS 17 commence par § ou B — jamais autre chose."""
        for nom, ex in EXIGENCES.items():
            if ex.source == SOURCE_IFRS17:
                self.assertRegex(
                    ex.reference, r'^(§|B\d)',
                    f"{nom} se dit IFRS 17 mais ne cite pas de paragraphe")
        print("    OK T1bis-c : toute exigence IFRS 17 cite un paragraphe")

    def test_reference_distingue_la_provenance(self):
        """Un livrable ne présente pas une règle maison comme la norme."""
        self.assertTrue(reference('courbe_dans_la_monnaie').startswith(
            'IFRS 17 §36 a), B79 — '))
        self.assertTrue(reference('devise_entite_invariante').startswith(
            'Règle ActuarIA ('))
        print("    OK T1bis-d : reference() prefixe differemment selon "
              "la provenance")


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


class T3bis_PlageDEmission(unittest.TestCase):
    """T3-bis — §22 vérifié plutôt que déclaré, sur la voie pré-agrégée.

    Sur un ensemble pré-agrégé, une seule date d'émission ne prouve rien :
    rien ne dit que l'ensemble ne réunit pas des contrats émis a quinze mois
    d'ecart. La plage le prouve — `max - min <= 1 an` EST la regle de §22.
    """

    def test_la_plage_debloque_la_verification_de_22(self):
        sans = capacites(MINIMAL + ('nb_contrats',))
        avec = capacites(MINIMAL + ('nb_contrats', 'date_emission_min',
                                    'date_emission_max'))
        self.assertTrue(sans['cohortes_annuelles'])
        self.assertFalse(sans['amplitude_cohorte_verifiee'])
        self.assertTrue(avec['amplitude_cohorte_verifiee'])
        gagnees = {n for n, ok in avec.items() if ok} - \
                  {n for n, ok in sans.items() if ok}
        self.assertEqual(gagnees, {'amplitude_cohorte_verifiee'})
        print("    OK T3bis : la plage debloque §22 VERIFIE, et rien d'autre")

    def test_une_seule_borne_ne_suffit_pas(self):
        """Une amplitude se mesure entre DEUX bornes."""
        for borne in ('date_emission_min', 'date_emission_max'):
            cap = capacites(MINIMAL + ('nb_contrats', borne))
            self.assertFalse(cap['amplitude_cohorte_verifiee'],
                             f"{borne} seule ne devrait rien prouver")
        print("    OK T3bis-b : une borne seule ne prouve rien")

    def test_constituer_et_verifier_sont_deux_exigences_distinctes(self):
        """⚠️ MEME HONNETETE QUE POUR §53 b) : une exigence absente vaut
        << declare, non etabli >>, jamais << conforme >>."""
        self.assertIn('cohortes_annuelles', EXIGENCES)
        self.assertIn('amplitude_cohorte_verifiee', EXIGENCES)
        self.assertIn('§22', EXIGENCES['cohortes_annuelles'].reference)
        self.assertEqual(EXIGENCES['amplitude_cohorte_verifiee'].reference,
                         '§22')
        self.assertIn('non déclarer',
                      EXIGENCES['amplitude_cohorte_verifiee'].libelle)
        self.assertIn('Sans objet',
                      EXIGENCES['amplitude_cohorte_verifiee'].libelle)
        print("    OK T3bis-c : CONSTITUER et VERIFIER sont deux exigences, "
              "et le libelle dit quand la seconde est sans objet")


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
