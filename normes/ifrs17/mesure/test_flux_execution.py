# -*- coding: utf-8 -*-
"""Tests S1 — les flux d'exécution : invariants internes et refus.

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️⚠️ AUCUN ORACLE ICI, ET CE FICHIER VERT NE VALIDE RIEN AUPRÈS D'UN TIERS.
Aucune source publiée disponible ne chiffre une valeur actualisée de flux
d'exécution avec ses hypothèses complètes. Ce que ces tests établissent est
INTERNE : des invariants arithmétiques (dégénérescence, monotonie, signe) et
des refus. C'est moins que C2, où l'oracle ICA mordait pour de vrai — et
c'est écrit ici pour qu'on ne confonde jamais les deux.
"""
import unittest

from normes.ifrs17.mesure.flux_execution import (
    ESPERANCE_CALCULEE,
    MONTANT_DECLARE,
    MOTIF_AJUSTEMENT_NEGATIF,
    MOTIF_ANNEE_HORS_COURBE,
    MOTIF_AUCUN_FLUX,
    MOTIF_AUCUN_SCENARIO,
    MOTIF_PROBABILITES,
    MOTIF_SANS_NIVEAU_CONFIANCE,
    MOTIF_SANS_SIGNATURE,
    MOTIF_SANS_SOURCE,
    Scenario,
    assembler,
    declarer_ajustement,
    declarer_courbe,
    esperance,
    montant_declare,
)
from normes.ifrs17.mesure.lrc_paa import RefusMesure

PLATE = {1: 0.02, 2: 0.02, 3: 0.02}


def _courbe(taux=None):
    return declarer_courbe(taux or PLATE, 'courbe interne, arrete 2026-12-31',
                           '2026-12-31', 'Selasse Sekle')


def _ajustement(montant=500.0):
    return declarer_ajustement(montant, 'quantile 75 %',
                               'cout du capital 6 %', '2026-12-31',
                               'Selasse Sekle')


def _flux():
    return [montant_declare(1, 1000.0), montant_declare(2, 800.0),
            montant_declare(3, 600.0)]


class T1_LesDeuxFormesDuFluxSeDistinguent(unittest.TestCase):
    """T1 — une espérance calculée et un montant remis ne valent pas pareil."""

    def test_l_esperance_se_calcule_sur_les_scenarios(self):
        f = esperance(1, [Scenario(1000.0, 0.5), Scenario(2000.0, 0.3),
                          Scenario(500.0, 0.2)])
        self.assertAlmostEqual(f.montant, 1000 * .5 + 2000 * .3 + 500 * .2, 9)
        self.assertEqual(f.base, ESPERANCE_CALCULEE)
        print(f"    OK S1 : esperance sur 3 scenarios = {f.montant:.0f}, "
              f"base {f.base}")

    def test_un_montant_remis_est_marque_et_le_resultat_le_porte(self):
        """⚠️ §33 a) EXIGE UNE ESPERANCE SUR L'EVENTAIL COMPLET. Un nombre
        remis seul PEUT en etre une, mais rien ne l'etablit -- et le
        presenter comme telle serait affirmer plus que la donnee ne porte.
        """
        r = assembler(_flux(), _courbe(), _ajustement())
        self.assertIn('PAS ÉTABLI', r.motif_esperance)
        self.assertIn('§33 a)', r.motif_esperance)
        print("    OK S1b : un montant declare marque le resultat entier "
              "-- le caractere probabilise n'est PAS etabli")

    def test_des_esperances_seules_ne_marquent_rien(self):
        flux = [esperance(a, [Scenario(1000.0 - 100 * a, 1.0)])
                for a in (1, 2, 3)]
        r = assembler(flux, _courbe(), _ajustement())
        self.assertEqual(r.motif_esperance, '')
        self.assertTrue(all(f.base == ESPERANCE_CALCULEE for f in flux))
        print("    OK S1c : que des esperances calculees -> aucun motif, "
              "§33 a) est etabli")

    def test_un_seul_montant_declare_suffit_a_marquer(self):
        """⚠️ LA MARQUE PORTE SUR LE RESULTAT, PAS SUR LA LIGNE. Un total
        dont un seul terme n'est pas etabli n'est pas etabli."""
        flux = [esperance(1, [Scenario(900.0, 1.0)]), montant_declare(2, 800.0)]
        r = assembler(flux, _courbe(), _ajustement())
        self.assertNotEqual(r.motif_esperance, '')
        self.assertEqual(flux[1].base, MONTANT_DECLARE)
        print("    OK S1d : 1 montant declare sur 2 -> le total est marque")


class T2_LesInvariantsInternes(unittest.TestCase):
    """T2 — ce qui se vérifie sans aucune source externe."""

    def test_a_taux_nul_l_actualisation_degenere_en_somme_brute(self):
        r = assembler(_flux(), _courbe({1: 0.0, 2: 0.0, 3: 0.0}),
                      _ajustement(0.0))
        self.assertAlmostEqual(r.valeur_actualisee, r.valeur_brute, 9)
        self.assertAlmostEqual(r.valeur_brute, 2400.0, 9)
        print(f"    OK S2 : a taux nul, actualisee = brute = "
              f"{r.valeur_brute:.0f}")

    def test_la_valeur_actualisee_decroit_quand_le_taux_monte(self):
        vals = [assembler(_flux(), _courbe({1: t, 2: t, 3: t}),
                          _ajustement(0.0)).valeur_actualisee
                for t in (0.0, 0.01, 0.02, 0.05, 0.10)]
        self.assertEqual(vals, sorted(vals, reverse=True))
        self.assertLess(vals[-1], vals[0])
        print(f"    OK S2b : monotonie verifiee sur 5 taux, "
              f"{vals[0]:.0f} -> {vals[-1]:.0f}")

    def test_l_ajustement_majore_toujours_le_passif(self):
        """⚠️ §37 : « l'indemnite QU'ELLE EXIGE ». Elle majore, jamais."""
        sans = assembler(_flux(), _courbe(), _ajustement(0.0))
        avec = assembler(_flux(), _courbe(), _ajustement(500.0))
        self.assertGreater(avec.total, sans.total)
        self.assertAlmostEqual(avec.total - sans.total, 500.0, 9)
        print(f"    OK S2c : l'ajustement majore le total de "
              f"{avec.total - sans.total:.0f}")

    def test_le_total_se_ventile_et_la_ventilation_porte_le_montant_SIGNE(self):
        """⚠️ LE DEFAUT QUE VULTURE A SIGNALE, ET C'EST LE MEME QU'EN C2-4.

        Verifier que l'ajustement MAJORE le total de 500 ne verifie pas que
        le champ PUBLIE porte 500. Une ventilation fausse dont le total tombe
        juste -- l'ajustement range ailleurs, ou remis a zero a la
        publication -- passerait sans que rien ne le voie. Un lecteur
        d'annexe lit la ventilation, pas le total.
        """
        a = _ajustement(500.0)
        r = assembler(_flux(), _courbe(), a)
        self.assertEqual(r.ajustement_risque, a.montant)
        self.assertAlmostEqual(r.valeur_actualisee + r.ajustement_risque,
                               r.total, 9)
        self.assertEqual(r.nb_periodes, 3)
        print(f"    OK S2e : total {r.total:.1f} = actualisee "
              f"{r.valeur_actualisee:.1f} + ajustement SIGNE "
              f"{r.ajustement_risque:.0f}")

    def test_l_actualisation_par_annee_n_est_pas_un_taux_plat_deguise(self):
        """⚠️ §36 a) PARLE DES CARACTERISTIQUES DE LIQUIDITE : une courbe
        par annee n'est pas un taux unique, et le calcul doit le refleter."""
        plate = assembler(_flux(), _courbe({1: .02, 2: .02, 3: .02}),
                          _ajustement(0.0)).valeur_actualisee
        pentue = assembler(_flux(), _courbe({1: .01, 2: .02, 3: .04}),
                           _ajustement(0.0)).valeur_actualisee
        self.assertNotAlmostEqual(plate, pentue, 6)
        print(f"    OK S2d : courbe plate {plate:.1f} vs pentue "
              f"{pentue:.1f} — la structure par terme opere")


class T3_LaDispenseDu59b(unittest.TestCase):
    """T3 — §59 b) dispense, il n'exclut pas."""

    def test_la_dispense_se_declare_et_se_publie(self):
        r = assembler(_flux(), None, _ajustement(), dispense_59b=True)
        self.assertFalse(r.actualisation_appliquee)
        self.assertAlmostEqual(r.valeur_actualisee, r.valeur_brute, 9)
        self.assertIn('§59 b)', r.motif_actualisation)
        self.assertIn('FACULTÉ', r.motif_actualisation)
        print("    OK S3 : dispense declaree -> non actualise, et le motif "
              "dit que c'est une faculte exercee")

    def test_sans_courbe_et_sans_dispense_la_mesure_est_refusee(self):
        """⚠️ LE POINT QUI SEPARE UN REFUS D'UN CHIFFRE FAUX. Rendre une
        valeur brute sans le signaler serait rendre un chiffre faux en
        silence."""
        with self.assertRaises(RefusMesure) as ctx:
            assembler(_flux(), None, _ajustement())
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_SOURCE)
        self.assertIn('§36', str(ctx.exception))
        print("    OK S3b : ni courbe ni dispense -> REFUS, jamais une "
              "valeur brute rendue en silence")


class T4_LesRefus(unittest.TestCase):
    """T4 — ce que le module refuse plutôt que de le fausser."""

    def test_des_probabilites_qui_ne_somment_pas_a_un(self):
        """⚠️ UN EVENTAIL TRONQUE REND UNE ESPERANCE BASSE, ET RIEN NE LE
        SIGNALERAIT. C'est l'erreur silencieuse type de ce calcul."""
        with self.assertRaises(RefusMesure) as ctx:
            esperance(1, [Scenario(1000.0, 0.5), Scenario(2000.0, 0.3)])
        self.assertEqual(ctx.exception.motif, MOTIF_PROBABILITES)
        self.assertIn('COMPLET', str(ctx.exception))
        print("    OK S4 : probabilites a 0,8 -> refus, l'eventail tronque "
              "est nomme")

    def test_un_eventail_vide_n_est_pas_une_esperance_nulle(self):
        with self.assertRaises(RefusMesure) as ctx:
            esperance(1, [])
        self.assertEqual(ctx.exception.motif, MOTIF_AUCUN_SCENARIO)
        print("    OK S4b : eventail vide -> refus, pas une esperance nulle")

    def test_aucun_flux_n_est_pas_un_total_nul(self):
        """⚠️⚠️ LE MOTIF DE TOUTE CETTE SESSION. Rendre 0 sur une liste vide
        serait la faute d'une gate rendant « Ran 0 tests » en sortant 0."""
        with self.assertRaises(RefusMesure) as ctx:
            assembler([], _courbe(), _ajustement())
        self.assertEqual(ctx.exception.motif, MOTIF_AUCUN_FLUX)
        self.assertIn('Ran 0 tests', str(ctx.exception))
        print("    OK S4c : aucun flux -> refus, jamais un total nul rendu "
              "comme un resultat")

    def test_une_annee_absente_de_la_courbe_est_refusee(self):
        """⚠️ EXTRAPOLER SERAIT INVENTER UNE HYPOTHESE QUE PERSONNE N'A
        SIGNEE ; IGNORER LE FLUX LE FERAIT DISPARAITRE."""
        with self.assertRaises(RefusMesure) as ctx:
            assembler(_flux(), _courbe({1: 0.02, 2: 0.02}), _ajustement())
        self.assertEqual(ctx.exception.motif, MOTIF_ANNEE_HORS_COURBE)
        self.assertIn('[3]', str(ctx.exception))
        print("    OK S4d : annee 3 absente de la courbe -> refus, l'annee "
              "manquante est nommee")

    def test_un_ajustement_negatif_est_refuse(self):
        with self.assertRaises(RefusMesure) as ctx:
            declarer_ajustement(-100.0, 'quantile 75 %', 'cout du capital',
                                '2026-12-31', 'Selasse Sekle')
        self.assertEqual(ctx.exception.motif, MOTIF_AJUSTEMENT_NEGATIF)
        self.assertIn('INDEMNITÉ EXIGÉE', str(ctx.exception))
        print("    OK S4e : ajustement negatif -> refus, §37 majore le "
              "passif et ne le reduit jamais")

    def test_un_ajustement_sans_niveau_de_confiance_est_refuse(self):
        """⚠️ §119 IMPOSE DE LE PUBLIER : un ajustement dont on ne peut pas
        dire a quel quantile il correspond n'est pas presentable."""
        with self.assertRaises(RefusMesure) as ctx:
            declarer_ajustement(500.0, '  ', 'cout du capital',
                                '2026-12-31', 'Selasse Sekle')
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_NIVEAU_CONFIANCE)
        self.assertIn('§119', str(ctx.exception))
        print("    OK S4f : ajustement sans niveau de confiance -> refus, "
              "§119 nomme")

    def test_une_courbe_sans_signataire_ou_sans_source_est_refusee(self):
        with self.assertRaises(RefusMesure) as ctx:
            declarer_courbe(PLATE, 'courbe interne', '2026-12-31', '  ')
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_SIGNATURE)
        with self.assertRaises(RefusMesure) as ctx:
            declarer_courbe(PLATE, '', '2026-12-31', 'Selasse Sekle')
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_SOURCE)
        print("    OK S4g : courbe sans signataire ou sans source -> refus")

    def test_une_courbe_vide_n_est_pas_une_courbe_plate_a_zero(self):
        with self.assertRaises(RefusMesure) as ctx:
            declarer_courbe({}, 'courbe interne', '2026-12-31', 'Selasse')
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_SOURCE)
        print("    OK S4h : courbe vide -> refus, ce n'est pas un taux nul")


class T5_AucuneDependanceHorsDuChantier(unittest.TestCase):
    """T5 — le module n'importe rien qui coûterait la gate non-vie."""

    def test_aucun_import_hors_du_paquet_ifrs17(self):
        """⚠️ MESURE, PAS PRINCIPE. `core/` est le seul noeud bidirectionnel
        du graphe d'imports du depot : en dependre condamnerait TOUT lot
        futur du chantier IFRS 17 a la gate non-vie de 24 minutes. Et un
        actuaire qui signe un ajustement pour risque ne signe pas << ce que
        tel agent avait sous la main >>.
        """
        import inspect

        from normes.ifrs17.mesure import flux_execution
        src = inspect.getsource(flux_execution)
        for interdit in ('import core', 'from core', 'direction_non_vie',
                         'direction_vie', 'direction_sante', 'courbe_rfr',
                         'a11_', 'a7_'):
            self.assertNotIn(interdit, src, interdit)
        print("    OK S5 : aucun import hors du chantier — la gate reste "
              "`normes` seule")


if __name__ == '__main__':
    unittest.main()
