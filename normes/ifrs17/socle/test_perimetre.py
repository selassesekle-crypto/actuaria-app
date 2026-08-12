# -*- coding: utf-8 -*-
"""Tests X1 — le périmètre publié, et ses contrôles de non-applicabilité.

⚠️ GATE : `py -m unittest discover -s normes -t .` — voir test_contrat.py.
"""
import re
import unittest

from normes.ifrs17.socle.contrat import EXIGENCES, SOURCE_IFRS17
from normes.ifrs17.socle.perimetre import (
    CONTROLES,
    COUVERT,
    ETATS,
    HORS_PERIMETRE,
    NON_CONSTRUIT,
    PERIMETRE,
    Element,
    elements,
    mention_directions,
    signaler,
    texte,
)


def _paragraphes(reference):
    """Les numéros de paragraphe cités par une référence."""
    return {('B' + b) if b else n
            for n, b in re.findall(r'§?(\d+)|B(\d+)', reference)}


class T1_LesTroisEtats(unittest.TestCase):
    """T1 — confondre « exclu » et « pas encore fait » tromperait deux fois."""

    def test_trois_etats_et_pas_deux(self):
        self.assertEqual(set(ETATS), {COUVERT, HORS_PERIMETRE,
                                      NON_CONSTRUIT})
        for etat in ETATS:
            self.assertTrue(elements(etat), f"état {etat} vide")
        detail = ' · '.join(f'{e} {len(elements(e))}' for e in ETATS)
        print(f"    OK T1 : {detail}")

    def test_une_exclusion_sans_raison_est_une_omission_deguisee(self):
        for e in PERIMETRE:
            if e.etat != COUVERT:
                self.assertTrue(e.raison.strip(),
                                f"{e.reference} ({e.etat}) sans raison")
        n = sum(1 for e in PERIMETRE if e.etat != COUVERT)
        print(f"    OK T1b : les {n} elements non couverts portent tous "
              f"leur raison")

    def test_aucun_etat_hors_vocabulaire(self):
        for e in PERIMETRE:
            self.assertIn(e.etat, ETATS, e.reference)
        with self.assertRaises(KeyError):
            elements('INVENTE')
        print(f"    OK T1c : {len(PERIMETRE)} elements, etats tous connus")


class T2_LePerimetreNeRevendiquePasPlusQueLeSocle(unittest.TestCase):
    """T2 — l'anti-dérive : la promesse ne peut pas dépasser le code."""

    def test_chaque_element_couvert_est_nomme_par_contrat_py(self):
        """⚠️ SANS CE VERROU, LA PROMESSE COMMERCIALE DERIVERAIT DU CODE.

        C'est le sens meme de ce module : un perimetre qui revendique une
        exigence que le socle ne nomme pas est un perimetre qui ment.
        """
        connus = set()
        for e in EXIGENCES.values():
            if e.source == SOURCE_IFRS17:
                connus |= _paragraphes(e.reference)
        for element in elements(COUVERT):
            cites = _paragraphes(element.reference)
            self.assertTrue(
                cites & connus,
                f"« {element.reference} » est declare COUVERT mais aucun de "
                f"ses paragraphes n'est nomme dans contrat.EXIGENCES")
        print(f"    OK T2 : les {len(elements(COUVERT))} elements couverts "
              f"sont adosses aux {len(EXIGENCES)} exigences du socle")

    def test_ce_qui_n_est_pas_construit_n_est_pas_declare_couvert(self):
        """La mesure PAA, la reassurance et la presentation ne sont PAS
        couvertes — les annoncer telles serait la faute inverse."""
        non_construits = ' '.join(e.reference for e in
                                  elements(NON_CONSTRUIT))
        for attendu in ('§55-59', '§60-70A', '§78-92', '§93-132'):
            self.assertIn(attendu, non_construits)
        couverts = ' '.join(e.reference for e in elements(COUVERT))
        for interdit in ('§55', '§60', '§80', '§100', '§130'):
            self.assertNotIn(interdit, couverts)
        print("    OK T2b : mesure, reassurance, presentation et annexes "
              "sont NON CONSTRUITES, jamais annoncees couvertes")


class T3_LesExclusionsQueLeTexteImpose(unittest.TestCase):
    """T3 — le relevé, et ce qu'il a ajouté à ma propre liste."""

    def test_le_test_du_champ_d_application_est_declare_non_fait(self):
        """⚠️ TROUVE EN RELISANT LE TEXTE, ABSENT DE MA LISTE INITIALE. La
        plateforme ne verifie JAMAIS qu'un contrat qu'on lui remet EST un
        contrat d'assurance (§3, §7, §8A, appendice A, B2-B30)."""
        champ = [e for e in PERIMETRE if '§3,' in e.reference]
        self.assertEqual(len(champ), 1)
        self.assertEqual(champ[0].etat, HORS_PERIMETRE)
        self.assertIn('ne vérifie pas', champ[0].libelle)
        self.assertIn('§8A', champ[0].raison)
        print("    OK T3 : le test du champ d'application est declare "
              "NON FAIT, avec sa raison")

    def test_les_trois_exclusions_du_cahier_des_charges(self):
        hors = {e.reference: e for e in elements(HORS_PERIMETRE)}
        self.assertIn('§32, §38-52', hors)                  # modèle général
        self.assertIn('annexe C', hors)                     # transition
        self.assertIn('B72 b) à e), B73', hors)             # révision B73
        b73 = hors['B72 b) à e), B73'].raison
        for mesure in ('cinq usages', 'ABSENTE en PAA', '§56', '§53 b)'):
            self.assertIn(mesure, b73)
        print("    OK T3b : les 3 exclusions portent leur raison mesuree")

    def test_les_flux_d_execution_sont_dus_en_PAA_pas_exclus(self):
        """⚠️ CE QUE §59 b) IMPOSE, ET QUE LE PÉRIMÈTRE DÉCLARAIT EXCLU.

        §59 b) : l'entité en PAA « DOIT evaluer le passif au titre des
        sinistres survenus [...] conformement aux paragraphes 33 a 37 et B36
        a B92 ». Choisir la PAA n'ecarte donc pas ces paragraphes, elle les
        appelle. Les ranger sous un << §32-52 hors perimetre >> les faisait
        passer pour ecartes quand ils sont dus.
        """
        refs = {e.reference: e for e in PERIMETRE}
        self.assertIn('§33-37, B36-B92', refs)
        flux = refs['§33-37, B36-B92']
        self.assertEqual(flux.etat, NON_CONSTRUIT)
        self.assertIn('§59 b)', flux.raison)
        hors = ' '.join(e.reference for e in elements(HORS_PERIMETRE))
        self.assertNotIn('§32-52', hors)
        for paragraphe in ('33', '34', '35', '36', '37'):
            self.assertNotIn(f'§{paragraphe},', hors)
        print("    OK T3d : §33-37 et B36-B92 sont NON CONSTRUITS et dus "
              "(§59 b), plus jamais declares hors perimetre")

    def test_l_option_OCI_se_declare_comme_methode_comptable(self):
        """Le §88 impose de CHOISIR : ne pas choisir n'est pas une option."""
        oci = next(e for e in PERIMETRE if '§88-89' in e.reference)
        self.assertIn('MÉTHODE COMPTABLE', oci.raison)
        self.assertIn('annexe', oci.raison)
        print("    OK T3c : l'option OCI est declaree comme methode "
              "comptable, a mentionner en annexe")


class T4_LesControlesDeNonApplicabilite(unittest.TestCase):
    """T4 — les drapeaux posés en D1 servent ici."""

    def test_aucune_alerte_sur_un_inventaire_ordinaire(self):
        lignes = [{'portefeuille': 'rc_auto', 'date_emission': '2026-03-15'}]
        self.assertEqual(signaler(lignes), ())
        print("    OK T4 : aucun faux positif sur un inventaire ordinaire")

    def test_un_contrat_a_participation_directe_est_signale(self):
        lignes = [{'portefeuille': 'epargne', 'participation_directe': 'oui'},
                  {'portefeuille': 'epargne', 'participation_directe': True},
                  {'portefeuille': 'rc_auto'}]
        alertes = signaler(lignes)
        self.assertEqual(len(alertes), 1)
        self.assertEqual(alertes[0].champ, 'participation_directe')
        self.assertEqual(alertes[0].nb_lignes, 2)
        self.assertIn('§45', alertes[0].reference)
        self.assertIn('HORS PÉRIMÈTRE', alertes[0].message)
        print(f"    OK T4b : {alertes[0].nb_lignes} contrats VFA signales, "
              f"{alertes[0].reference}")

    def test_une_composante_d_investissement_est_signalee(self):
        alertes = signaler([{'composante_investissement': 'VRAI'}])
        self.assertEqual(alertes[0].reference, '§85')
        self.assertIn('exclue des produits', alertes[0].message)
        print("    OK T4c : composante d'investissement signalee (§85)")

    def test_le_drapeau_se_lit_quelle_que_soit_son_ecriture(self):
        for valeur in ('oui', 'OUI', 'Oui', 'yes', 'true', 'VRAI', '1', 'x',
                       True):
            self.assertEqual(len(signaler(
                [{'participation_directe': valeur}])), 1, repr(valeur))
        for valeur in ('non', 'no', 'false', '0', '', None, False):
            self.assertEqual(signaler([{'participation_directe': valeur}]),
                             (), repr(valeur))
        print("    OK T4d : 9 ecritures du drapeau lues, 7 negations "
              "correctement ignorees")

    def test_signaler_ne_refuse_jamais(self):
        """Un inventaire PEUT contenir des contrats qu'on ne mesure pas ;
        ce qui serait fautif, c'est de les mesurer quand meme."""
        alertes = signaler([{'participation_directe': 'oui'}])
        self.assertIsInstance(alertes, tuple)
        self.assertEqual(set(CONTROLES), {'participation_directe',
                                          'composante_investissement'})
        print("    OK T4e : signaler() rend des alertes, ne leve jamais")


class T5_LaMentionDePerimetrePartiel(unittest.TestCase):
    """T5 — un jeu partiel pris pour un jeu complet est ce qu'un CAC relève."""

    def test_une_seule_direction(self):
        m = mention_directions(['Non-Vie'])
        self.assertIn('limités aux groupes de la direction Non-Vie', m)
        self.assertIn('périmètre partiel', m)
        print(f"    OK T5 : « {m} »")

    def test_plusieurs_directions(self):
        m = mention_directions(['Santé-Prévoyance', 'Non-Vie'])
        self.assertIn('Non-Vie, Santé-Prévoyance', m)
        self.assertIn('périmètre partiel', m)
        print("    OK T5b : plusieurs directions, mention triee et partielle")

    def test_aucune_direction_leve(self):
        with self.assertRaises(ValueError):
            mention_directions([])
        print("    OK T5c : des etats portent toujours sur un perimetre")


class T6_LeTextePublie(unittest.TestCase):
    """T6 — ce qui se remet à un actuaire ou à un commissaire."""

    def test_le_texte_porte_les_trois_sections_et_les_raisons(self):
        t = texte()
        for attendu in ('PÉRIMÈTRE IFRS 17', 'CE QUI EST COUVERT',
                        'PAS ENCORE CONSTRUIT', 'DÉCISIONS ASSUMÉES',
                        'SIGNALÉS par'):
            self.assertIn(attendu, t)
        for e in elements(HORS_PERIMETRE):
            self.assertIn(e.reference, t)
        print(f"    OK T6 : {len(texte().splitlines())} lignes, "
              "3 sections, toutes les references citees")

    def test_aucun_element_n_est_oublie_du_texte(self):
        t = texte()
        for e in PERIMETRE:
            self.assertIn(e.libelle.split('\n')[0][:40], t, e.reference)
        self.assertEqual(set(Element._fields),
                         {'reference', 'etat', 'libelle', 'raison'})
        print(f"    OK T6b : les {len(PERIMETRE)} elements figurent au texte")


if __name__ == '__main__':
    unittest.main(verbosity=2)
