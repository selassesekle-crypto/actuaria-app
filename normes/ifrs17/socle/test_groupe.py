# -*- coding: utf-8 -*-
"""Tests U1a — la dérivation des groupes, l'unité de compte d'IFRS 17.

⚠️ GATE : `py -m unittest discover -s normes -t .` — voir test_contrat.py.
"""
import unittest
from datetime import date

from normes.ifrs17.socle.groupe import (
    CLASSE_16A, CLASSE_16C, CLASSE_PAR_DEFAUT, CONVENTION_CALENDAIRE,
    MOTIF_AMPLITUDE_22, MOTIF_CHEVAUCHE_COHORTES, MOTIF_SANS_EMISSION,
    MOTIF_SANS_PORTEFEUILLE, PAA_ELIGIBLE, PAA_NON_ELIGIBLE, PAA_NON_ETABLI,
    TRACE_16B_NON_DECLARE, CleGroupe, Groupe, RefusGroupe, cohorte,
    convention_exercice, deriver, resume)


def _ligne(**kw):
    """Une ligne d'inventaire canonique, avec des valeurs plausibles."""
    base = {'portefeuille': 'rc_auto', 'date_emission': '2026-03-15',
            'debut_couverture': '2026-04-01', 'fin_couverture': '2027-03-31'}
    base.update(kw)
    return base


class T1_LaCle(unittest.TestCase):
    """T1 — portefeuille × classe §16 × cohorte."""

    def test_trois_etages_forment_la_cle(self):
        gs = deriver([
            _ligne(portefeuille='rc_auto'),
            _ligne(portefeuille='mrh'),
            _ligne(portefeuille='rc_auto', date_emission='2025-03-15',
                   debut_couverture='2025-04-01',
                   fin_couverture='2026-03-31'),
            _ligne(portefeuille='rc_auto',
                   classe_profitabilite=CLASSE_16A),
        ])
        self.assertEqual({g.cle.texte for g in gs}, {
            'rc_auto|AUTRES|2026', 'mrh|AUTRES|2026',
            'rc_auto|AUTRES|2025', 'rc_auto|DEFICITAIRE|2026'})
        print(f"    OK T1 : 4 lignes -> {len(gs)} groupes, "
              "un par combinaison des trois etages")

    def test_les_groupes_sortent_tries(self):
        gs = deriver([_ligne(portefeuille=p) for p in ('mrh', 'auto', 'zzz')])
        self.assertEqual([g.cle for g in gs], sorted(g.cle for g in gs))
        print("    OK T1b : groupes tries par cle")

    def test_aucun_montant_dans_le_groupe(self):
        """⚠️ LA FRONTIERE AVEC LE MAGASIN DE CLOTURES, VERROUILLEE.

        Le registre repond a << quels groupes existent >>, le magasin a
        << combien valaient-ils >>. Un champ monetaire ici ferait fuir la
        seconde question dans le premier objet.
        """
        self.assertEqual(set(Groupe._fields), {
            'cle', 'date_compta_25', 'origine_date_25', 'eligibilite_paa',
            'motif_eligibilite', 'nb_lignes', 'traces'})
        for interdit in ('prime', 'montant', 'be', 'lrc', 'lic', 'total',
                         'euros', 'valeur'):
            for champ in Groupe._fields:
                self.assertNotIn(interdit, champ)
        print(f"    OK T1c : {len(Groupe._fields)} champs, aucun monetaire")


class T2_LaConventionDeCohorte(unittest.TestCase):
    """T2 — §22 pose une contrainte glissante ; l'annee civile est un usage."""

    def test_calendaire_et_exercice_decale_donnent_des_cohortes_differentes(self):
        d = date(2026, 2, 15)
        self.assertEqual(cohorte(CONVENTION_CALENDAIRE, d), '2026')
        self.assertEqual(cohorte(convention_exercice(4), d), '2025-26')
        print("    OK T2 : 15/02/2026 -> cohorte 2026 en calendaire, "
              "2025-26 en exercice avril-mars")

    def test_la_convention_deplace_les_groupes(self):
        """La meme population, deux conventions, deux decoupages.

        Quatre emissions : novembre 2025, janvier, fevrier et juin 2026.
        En annee civile elles se repartissent 1 / 3 ; en exercice avril-mars
        elles se repartissent 3 / 1 — les MEMES contrats, des groupes
        differents. C'est pourquoi la convention se declare.
        """
        pop = [_ligne(date_emission=d, debut_couverture=d,
                      fin_couverture=None)
               for d in ('2025-11-20', '2026-01-10', '2026-02-28',
                         '2026-06-30')]
        cal = deriver(pop, convention=CONVENTION_CALENDAIRE)
        exo = deriver(pop, convention=convention_exercice(4))
        self.assertEqual({g.cle.cohorte: g.nb_lignes for g in cal},
                         {'2025': 1, '2026': 3})
        self.assertEqual({g.cle.cohorte: g.nb_lignes for g in exo},
                         {'2025-26': 3, '2026-27': 1})
        print(f"    OK T2b : calendaire {[g.nb_lignes for g in cal]} vs "
              f"exercice {[g.nb_lignes for g in exo]} — "
              "memes contrats, groupes differents")

    def test_un_mois_de_debut_invalide_est_refuse(self):
        for m in (0, 13, -1):
            with self.assertRaises(ValueError):
                convention_exercice(m)
        self.assertIs(convention_exercice(1), CONVENTION_CALENDAIRE)
        print("    OK T2c : mois hors [1,12] refuse ; 1 = calendaire")


class T3_LesDeuxControlesDu22(unittest.TestCase):
    """T3 — sur la voie pre-agregee, l'amplitude ne suffit pas."""

    def test_amplitude_superieure_a_un_an_refusee(self):
        with self.assertRaises(RefusGroupe) as ctx:
            deriver([_ligne(nb_contrats=2140, date_emission_min='2024-06-01',
                            date_emission_max='2025-09-30')])
        self.assertEqual(ctx.exception.motif, MOTIF_AMPLITUDE_22)
        self.assertIn('§22', str(ctx.exception))
        print("    OK T3 : amplitude > 1 an refusee")

    def test_un_ensemble_court_qui_chevauche_deux_cohortes_est_refuse(self):
        """⚠️ LE CONTROLE QUE L'AMPLITUDE SEULE NE VOIT PAS. Trois mois, donc
        `max - min <= 1 an` tenu — mais deux cohortes calendaires."""
        with self.assertRaises(RefusGroupe) as ctx:
            deriver([_ligne(nb_contrats=800, date_emission='2025-11-15',
                            date_emission_min='2025-11-15',
                            date_emission_max='2026-02-20')])
        self.assertEqual(ctx.exception.motif, MOTIF_CHEVAUCHE_COHORTES)
        self.assertIn('2025', str(ctx.exception))
        self.assertIn('2026', str(ctx.exception))
        print("    OK T3b : 3 mois d'amplitude mais 2 cohortes -> refuse")

    def test_le_meme_ensemble_passe_sous_une_autre_convention(self):
        """⚠️ C'EST CE QUI REND LA CONVENTION OPERANTE. Novembre-fevrier
        chevauche deux annees civiles, pas un exercice avril-mars."""
        ligne = _ligne(nb_contrats=800, date_emission='2025-11-15',
                       date_emission_min='2025-11-15',
                       date_emission_max='2026-02-20')
        with self.assertRaises(RefusGroupe):
            deriver([ligne], convention=CONVENTION_CALENDAIRE)
        gs = deriver([ligne], convention=convention_exercice(4))
        self.assertEqual(len(gs), 1)
        self.assertEqual(gs[0].cle.cohorte, '2025-26')
        print("    OK T3c : refuse en calendaire, accepte en avril-mars — "
              "la convention n'est pas decorative")

    def test_sans_plage_le_22_est_declare_non_etabli(self):
        gs = deriver([_ligne(nb_contrats=800)])
        self.assertTrue(any('DÉCLARÉ, non établi' in t for t in gs[0].traces))
        print("    OK T3d : sans plage, §22 est trace comme DECLARE")


class T4_Eligibilite53(unittest.TestCase):
    """T4 — le verdict §53 b), et ses trois etats."""

    def test_couverture_annuelle_eligible(self):
        gs = deriver([_ligne(debut_couverture='2026-04-01',
                             fin_couverture='2027-03-31')])
        self.assertEqual(gs[0].eligibilite_paa, PAA_ELIGIBLE)
        self.assertIn('vérifié, et non déclaré', gs[0].motif_eligibilite)
        print("    OK T4 : couverture d'un an -> ELIGIBLE, verifie")

    def test_un_seul_contrat_trop_long_ferme_la_porte_b(self):
        """§53 b) porte sur CHACUN des contrats du groupe."""
        gs = deriver([_ligne(), _ligne(debut_couverture='2026-04-01',
                                       fin_couverture='2029-03-31')])
        self.assertEqual(gs[0].eligibilite_paa, PAA_NON_ELIGIBLE)
        self.assertIn('1 contrat(s) sur 2', gs[0].motif_eligibilite)
        self.assertIn('signalé, non évalué', gs[0].motif_eligibilite)
        print("    OK T4b : 1 contrat sur 2 trop long -> groupe NON ELIGIBLE, "
              "signale et non evalue")

    def test_couverture_indeterminee_ferme_la_porte_b(self):
        gs = deriver([_ligne(fin_couverture='INDETERMINEE')])
        self.assertEqual(gs[0].eligibilite_paa, PAA_NON_ELIGIBLE)
        self.assertIn('sans terme excède un an', gs[0].motif_eligibilite)
        print("    OK T4c : couverture indeterminee -> §53 b) ferme")

    def test_sans_fin_de_couverture_le_verdict_est_NON_ETABLI(self):
        """⚠️ NON_ETABLI N'EST PAS ELIGIBLE — c'est l'aveu qu'on ne sait pas."""
        gs = deriver([_ligne(fin_couverture=None)])
        self.assertEqual(gs[0].eligibilite_paa, PAA_NON_ETABLI)
        self.assertIn('DÉCLARÉ, non établi', gs[0].motif_eligibilite)
        self.assertNotEqual(gs[0].eligibilite_paa, PAA_ELIGIBLE)
        print("    OK T4d : sans fin de couverture -> NON_ETABLI, "
              "distinct d'ELIGIBLE")


class T5_Date25(unittest.TestCase):
    """T5 — la premiere des trois dates, et ce qui n'est pas evaluable."""

    def test_le_plus_petit_debut_de_couverture(self):
        gs = deriver([_ligne(debut_couverture='2026-04-01'),
                      _ligne(debut_couverture='2026-02-01',
                             date_emission='2026-01-05')])
        self.assertEqual(gs[0].date_compta_25, date(2026, 2, 1))
        self.assertIn('§25 a)', gs[0].origine_date_25)
        self.assertIn("b) et c) ne sont pas évaluables",
                      gs[0].origine_date_25)
        print(f"    OK T5 : §25 = {gs[0].date_compta_25}, "
              "et les deux autres criteres sont NOMMES non evaluables")

    def test_sans_debut_de_couverture_la_date_25_n_est_pas_etablie(self):
        """⚠️ LE FICHIER MINIMAL DE 4 COLONNES NE PORTE PAS `debut_couverture`."""
        gs = deriver([_ligne(debut_couverture=None)])
        self.assertIsNone(gs[0].date_compta_25)
        self.assertIn('non établie', gs[0].origine_date_25)
        print("    OK T5b : sans debut_couverture, §25 est NON ETABLIE "
              "-- pas devinee")


class T6_Classe16(unittest.TestCase):
    """T6 — la presomption de §18, et la trace qui la dit."""

    def test_le_defaut_est_AUTRES_et_la_trace_le_dit(self):
        gs = deriver([_ligne()])
        self.assertEqual(gs[0].cle.classe_16, CLASSE_16C)
        self.assertEqual(CLASSE_PAR_DEFAUT, CLASSE_16C)
        self.assertIn(TRACE_16B_NON_DECLARE, gs[0].traces)
        self.assertIn('§18', TRACE_16B_NON_DECLARE)
        print("    OK T6 : defaut = AUTRES, presomption §18 tracee")

    def test_une_classe_declaree_est_respectee_sans_trace(self):
        gs = deriver([_ligne(classe_profitabilite=CLASSE_16A)])
        self.assertEqual(gs[0].cle.classe_16, CLASSE_16A)
        self.assertNotIn(TRACE_16B_NON_DECLARE, gs[0].traces)
        print("    OK T6b : classe declaree respectee, aucune trace §16(b)")

    def test_un_critere_declare_supprime_la_trace(self):
        gs = deriver([_ligne()], critere_16b_declare=True)
        self.assertNotIn(TRACE_16B_NON_DECLARE, gs[0].traces)
        print("    OK T6c : critere §16(b) declare -> plus de trace")


class T7_Refus(unittest.TestCase):
    """T7 — il n'y a pas de groupe partiel."""

    def test_sans_portefeuille(self):
        with self.assertRaises(RefusGroupe) as ctx:
            deriver([_ligne(portefeuille='')])
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_PORTEFEUILLE)
        print("    OK T7 : refus sans portefeuille (§14)")

    def test_date_d_emission_illisible(self):
        with self.assertRaises(RefusGroupe) as ctx:
            deriver([_ligne(date_emission='Q2 2026')])
        self.assertEqual(ctx.exception.motif, MOTIF_SANS_EMISSION)
        print("    OK T7b : refus sur une date d'emission illisible")

    def test_le_resume_dit_ce_qui_a_ete_derive(self):
        gs = deriver([_ligne(), _ligne(portefeuille='mrh')])
        txt = resume(gs)
        self.assertIn('GROUPES DÉRIVÉS — 2', txt)
        self.assertIn('année civile', txt)
        self.assertIn('§25', txt)
        self.assertIn('§53', txt)
        print("    OK T7c : le resume nomme la convention et les paragraphes")


class T8_CleGroupeEstStable(unittest.TestCase):
    """T8 — la clé est scellée : elle doit être comparable et ordonnable."""

    def test_la_cle_est_un_triplet_ordonnable_et_imprimable(self):
        a = CleGroupe('rc_auto', CLASSE_16C, '2025')
        b = CleGroupe('rc_auto', CLASSE_16C, '2026')
        self.assertLess(a, b)
        self.assertEqual(b.texte, 'rc_auto|AUTRES|2026')
        self.assertEqual(a, CleGroupe('rc_auto', CLASSE_16C, '2025'))
        print("    OK T8 : cle ordonnable, comparable, imprimable")


if __name__ == '__main__':
    unittest.main(verbosity=2)
