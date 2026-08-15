# -*- coding: utf-8 -*-
"""Tests M1 — le §55 confronté à l'oracle ICA 5.2, et aux refus.

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️ C'EST ICI QUE L'ORACLE MORD POUR LA PREMIÈRE FOIS. Le fichier
`oracles/test_ica_222092.py` ne vérifiait que la source ; celui-ci confronte
un calcul du dépôt à des valeurs venues du dehors.
"""
import unittest

from normes.ifrs17.mesure.lrc_paa import (
    MOTIF_BASE_DE_PRIME_NON_DECLAREE,
    MOTIF_DUREE_INVALIDE,
    MOTIF_FINANCEMENT_NON_CONSTRUIT,
    MOTIF_MONTANT_NEGATIF,
    MOTIF_PRORATA_DEUX_FOIS,
    MOTIF_SEPARATION_NON_FOURNIE,
    MOTIF_VERDICT_53_53A_NON_EVALUEE,
    MOTIF_VERDICT_53_NON_DECLARE,
    MOTIF_VERDICT_53_NON_ETABLI,
    PRIME_DEJA_PRORATISEE,
    PRIME_NOMINALE,
    VERDICT_53_53A_NON_EVALUEE,
    VERDICT_53_ELIGIBLE,
    VERDICT_53_NON_ETABLI,
    RefusMesure,
    lrc_initial,
    lrc_suivant,
    periode_annuelle,
    revenue_depuis_fraction,
    revenue_prorata_temporis,
)
from normes.ifrs17.oracles.ica_222092 import (
    ATTENDU_5_2,
    ENTREE_5_2,
    SOURCE,
    TOLERANCE,
)


def _mesure_5_2():
    """L'exemple 5.2 mesuré par la plateforme, sans rien lui souffler."""
    e = ENTREE_5_2
    return periode_annuelle(
        primes_attendues=e['prime'],
        duree_couverture=e['duree_couverture_ans'],
        frais_acquisition_attribuables=e['frais_acquisition_attribuables'],
        frais_maintenance_attribuables=e['frais_maintenance_attribuables_an1'],
        frais_non_attribuables=(e['frais_acquisition_non_attribuables']
                                + e['frais_maintenance_non_attribuables_par_an']),
        sinistres_survenus=0.0,
        verdict_53_declare=VERDICT_53_ELIGIBLE)


class T1_LOracle5_2(unittest.TestCase):
    """T1 — les six postes de la source, face au calcul du dépôt."""

    def test_les_six_postes_tombent_sur_l_oracle(self):
        p, a = _mesure_5_2(), ATTENDU_5_2
        for poste, obtenu, attendu in (
                ('insurance_revenue', p.revenue, a['insurance_revenue']),
                ('insurance_service_expenses', p.charges_service,
                 a['insurance_service_expenses']),
                ('insurance_service_result', p.service_result,
                 a['insurance_service_result']),
                ('autres_charges', p.autres_charges, a['autres_charges']),
                ('resultat', p.resultat, a['resultat']),
                ('LRC', p.lrc_cloture, a['lrc'])):
            self.assertLessEqual(
                abs(obtenu - attendu), TOLERANCE,
                f"{poste} : mesure {obtenu}, oracle {attendu}")
        print(f"    OK M1 : les 6 postes de 5.2 tombent sur l'oracle "
              f"(tolerance {TOLERANCE}) — source : {SOURCE[:34]}...")

    def test_le_LRC_vaut_400_et_non_500(self):
        """⚠️ LE POSTE QUE CET ORACLE A ETE CHOISI POUR ATTRAPER.

        Les frais d'acquisition non amortis ne forment PAS un actif separe :
        ils diminuent le LRC. Une implementation qui les logerait ailleurs
        rendrait 500, avec un bilan qui equilibre quand meme -- une erreur
        qu'aucun controle de coherence interne ne verrait.
        """
        p = _mesure_5_2()
        self.assertAlmostEqual(p.lrc_cloture, 400.0, 6)
        self.assertNotAlmostEqual(p.lrc_cloture, 500.0, 6)
        print(f"    OK M1b : LRC = {p.lrc_cloture:.0f}, et non 500")

    def test_le_roll_forward_du_55_b_se_lit_terme_a_terme(self):
        """800 + 100 − 500 = 400. ⚠️ L'AMORTISSEMENT AUGMENTE LE LRC : il
        annule la soustraction du §55 a) a mesure qu'il passe en charges."""
        e = ENTREE_5_2
        ouverture = lrc_initial(e['prime'],
                                e['frais_acquisition_attribuables'],
                                verdict_53_declare=VERDICT_53_ELIGIBLE)
        self.assertAlmostEqual(ouverture, 800.0, 6)
        cloture = lrc_suivant(
            ouverture,
            amortissement_frais_acquisition=(
                e['frais_acquisition_attribuables']
                / e['duree_couverture_ans']),
            revenue_periode=revenue_prorata_temporis(
                e['prime'], e['duree_couverture_ans']),
            verdict_53_declare=VERDICT_53_ELIGIBLE)
        self.assertAlmostEqual(cloture, ATTENDU_5_2['lrc'], 6)
        print(f"    OK M1c : §55 a) {ouverture:.0f} -> §55 b) "
              f"{cloture:.0f}, terme a terme")

    def test_les_frais_non_attribuables_sortent_du_resultat_d_assurance(self):
        """⚠️ LES OUBLIER GONFLERAIT LE RESULTAT D'ASSURANCE DE 55."""
        p = _mesure_5_2()
        self.assertAlmostEqual(p.autres_charges, 55.0, 6)
        self.assertAlmostEqual(p.service_result - p.autres_charges,
                               p.resultat, 6)
        self.assertNotAlmostEqual(p.service_result, p.resultat, 6)
        print(f"    OK M1d : {p.autres_charges:.0f} de frais non "
              f"attribuables hors du resultat d'assurance")


class T1b_LaSeparationNonFournie(unittest.TestCase):
    """T1b — « on ne sait pas » ne doit pas ressembler à « zéro »."""

    def test_sans_separation_le_resultat_n_est_pas_etabli(self):
        """⚠️ LA LECON DE `PAA_NON_ETABLI`, APPLIQUEE A LA MESURE.

        La separation attribuable / non attribuable releve d'une decision
        comptable de l'entite, pas d'une regle calculable : ce module ne la
        devine pas. Mais ne pas la fournir ne doit PAS rendre un resultat
        egal au resultat d'assurance -- ce serait publier un total gonfle de
        tous les frais non attribuables, 55 sur l'exemple ICA 5.2, sans que
        rien ne le signale.
        """
        e = ENTREE_5_2
        p = periode_annuelle(
            primes_attendues=e['prime'],
            duree_couverture=e['duree_couverture_ans'],
            frais_acquisition_attribuables=e['frais_acquisition_attribuables'],
            frais_maintenance_attribuables=(
                e['frais_maintenance_attribuables_an1']),
            verdict_53_declare=VERDICT_53_ELIGIBLE)
        self.assertIsNone(p.resultat)
        self.assertIsNone(p.autres_charges)
        self.assertEqual(p.motif_resultat, MOTIF_SEPARATION_NON_FOURNIE)
        self.assertIn('NON FOURNIE', p.motif_resultat)
        # ce qui EST etabli le reste : le LRC et le resultat d'assurance
        self.assertAlmostEqual(p.lrc_cloture, ATTENDU_5_2['lrc'], 6)
        self.assertAlmostEqual(p.service_result,
                               ATTENDU_5_2['insurance_service_result'], 6)
        print("    OK M1e : sans separation -> resultat NON ETABLI et "
              "motive ; le LRC et le resultat d'assurance restent etablis")

    def test_zero_fourni_n_est_pas_absence(self):
        """⚠️ `0.0` AFFIRME QU'IL N'Y A AUCUN FRAIS NON ATTRIBUABLE. C'est
        une declaration, pas une absence -- et elle s'honore."""
        e = ENTREE_5_2
        commun = {'primes_attendues': e['prime'],
                  'duree_couverture': e['duree_couverture_ans'],
                  'verdict_53_declare': VERDICT_53_ELIGIBLE}
        declare = periode_annuelle(frais_non_attribuables=0.0, **commun)
        tu = periode_annuelle(**commun)
        self.assertEqual(declare.autres_charges, 0.0)
        self.assertIsNotNone(declare.resultat)
        self.assertEqual(declare.motif_resultat, '')
        self.assertIsNone(tu.resultat)
        print("    OK M1f : 0.0 declare -> resultat etabli ; absent -> "
              "non etabli. Les deux ne se confondent pas")


class T1c_LeProrataNeSAppliquePasDeuxFois(unittest.TestCase):
    """T1c — le seul chemin par lequel l'ajustement peut être doublé."""

    def test_une_prime_deja_proratisee_refuse_une_fraction(self):
        """⚠️⚠️ MESURE, PAS SUPPOSITION. Sur les 2 000 contrats remis,
        `revenue_cumule = prime_attendue x fraction_acquise` tient a 0,0000
        pres -- maximum, minimum et moyenne des ecarts tous nuls. Le prorata
        est DEJA dans la donnee. Lui appliquer une fraction le compterait
        deux fois, et rien dans les NOMBRES ne le dirait : seule la
        declaration de l'appelant le distingue.
        """
        with self.assertRaises(RefusMesure) as ctx:
            revenue_depuis_fraction(prime=320.37,
                                    base_prime=PRIME_DEJA_PRORATISEE,
                                    fraction_acquise=0.58)
        self.assertEqual(ctx.exception.motif, MOTIF_PRORATA_DEUX_FOIS)
        self.assertIn('DEUX FOIS', str(ctx.exception))
        self.assertIn('0,0000', str(ctx.exception))
        print("    OK M1g : prime deja proratisee + fraction -> REFUS, et le "
              "message porte la mesure qui le fonde")

    def test_une_prime_nominale_accepte_la_fraction(self):
        obtenu = revenue_depuis_fraction(prime=1000.0,
                                         base_prime=PRIME_NOMINALE,
                                         fraction_acquise=0.5)
        self.assertAlmostEqual(obtenu, 500.0, 9)
        print(f"    OK M1h : prime nominale x 0,5 = {obtenu:.0f}")

    def test_une_base_non_declaree_est_refusee(self):
        """⚠️ DEUX GRANDEURS DIFFERENTES, ET RIEN DANS LE NOMBRE NE LES
        DISTINGUE. D'ou une declaration, comme pour le taux verrouille,
        l'attribution des couts et le declenchement du §57."""
        for base in (None, '', 'brute'):
            with self.assertRaises(RefusMesure) as ctx:
                revenue_depuis_fraction(prime=1000.0, base_prime=base,
                                        fraction_acquise=0.5)
            self.assertEqual(ctx.exception.motif,
                             MOTIF_BASE_DE_PRIME_NON_DECLAREE)
        print("    OK M1i : base de prime non declaree -> refus")

    def test_une_fraction_hors_bornes_est_refusee(self):
        """Au-dela de 1, elle produirait un revenu superieur a la prime."""
        for f in (-0.1, 1.5):
            with self.assertRaises(RefusMesure) as ctx:
                revenue_depuis_fraction(prime=1000.0,
                                        base_prime=PRIME_NOMINALE,
                                        fraction_acquise=f)
            self.assertEqual(ctx.exception.motif,
                             'fraction_acquise_hors_bornes')
        print("    OK M1j : fraction hors [0, 1] refusee")


class T1d_LaDureeNEstPasEnAnneesEntieres(unittest.TestCase):
    """T1d — la correction de vocabulaire, et ce qu'elle pèse."""

    def test_une_duree_fractionnaire_est_acceptee(self):
        """⚠️ NI §55 b) NI B126 NE CONNAISSENT L'ANNEE ENTIERE. Le premier
        deroule << a la fin de chaque PERIODE DE REPORTING >>, le second
        repartit << en fonction de l'ECOULEMENT DU TEMPS >>. La contrainte
        d'annees entieres etait la MIENNE, et le nom `duree_ans` pretait a
        la norme une exigence qu'elle n'a pas."""
        p = periode_annuelle(primes_attendues=320.37, duree_couverture=0.582,
                             frais_non_attribuables=0.0,
                             verdict_53_declare=VERDICT_53_ELIGIBLE)
        self.assertGreater(p.revenue, 0)
        self.assertAlmostEqual(p.revenue, 320.37 / 0.582, 6)
        print(f"    OK M1k : duree 0,582 acceptee, revenue "
              f"{p.revenue:.2f} par unite de temps")

    def test_le_module_ECRIT_ce_que_le_fractionnaire_pese(self):
        """⚠️ POUR QUE PERSONNE NE ROUVRE LE SUJET EN CROYANT QU'IL EST GROS.
        6,7 % des lignes, 0,55 % du LRC -- l'inverse du portefeuille DO, ou
        100 contrats portaient 86 % du passif."""
        from normes.ifrs17.mesure import lrc_paa
        doc = lrc_paa.__doc__
        self.assertIn('6,7 % DES LIGNES', doc)
        self.assertIn('0,55 % DU LRC', doc)
        self.assertIn("n'est jamais une mesure de matérialité", doc)
        print("    OK M1l : le module ecrit 6,7 % des lignes contre 0,55 % "
              "du LRC")


class T2_LesRefus(unittest.TestCase):
    """T2 — ce que le module refuse de mesurer plutôt que de le fausser."""

    def test_les_TROIS_etats_du_53_ont_TROIS_motifs_distincts(self):
        """⚠️⚠️ LE BOOLEEN ECRASAIT TROIS ETATS EN DEUX.

        `NON_ETABLI` et `53A_NON_EVALUEE` devenaient tous deux `False`,
        indiscernables l'un de l'autre ET d'un refus franc. C'est le nom du
        motif que consomment les agregats : trois etats, trois noms.
        """
        attendus = {
            '': MOTIF_VERDICT_53_NON_DECLARE,
            VERDICT_53_NON_ETABLI: MOTIF_VERDICT_53_NON_ETABLI,
            VERDICT_53_53A_NON_EVALUEE: MOTIF_VERDICT_53_53A_NON_EVALUEE,
        }
        for verdict, motif in attendus.items():
            with self.assertRaises(RefusMesure, msg=verdict) as ctx:
                lrc_initial(1000.0, 200.0, verdict_53_declare=verdict)
            self.assertEqual(ctx.exception.motif, motif, msg=verdict)
        self.assertEqual(len(set(attendus.values())), 3)
        print("    OK M2 : trois etats du §53 -> trois motifs distincts")

    def test_le_refus_distingue_l_AVEU_de_la_PORTE_OUVERTE(self):
        """⚠️ Un aveu d'ignorance et une porte ouverte en droit ne sont pas
        la meme chose, et aucun des deux n'est un refus d'eligibilite."""
        with self.assertRaises(RefusMesure) as a:
            lrc_initial(1000.0, 200.0,
                        verdict_53_declare=VERDICT_53_NON_ETABLI)
        self.assertIn('AVEU', str(a.exception))
        with self.assertRaises(RefusMesure) as b:
            lrc_initial(1000.0, 200.0,
                        verdict_53_declare=VERDICT_53_53A_NON_EVALUEE)
        self.assertIn('OUVERTE EN DROIT', str(b.exception))
        self.assertIn('§54', str(b.exception))

    def test_ELIGIBLE_laisse_mesurer(self):
        self.assertAlmostEqual(
            lrc_initial(1000.0, 200.0,
                        verdict_53_declare=VERDICT_53_ELIGIBLE), 800.0)

    def test_un_financement_significatif_est_refuse_pas_ignore(self):
        """⚠️ LE POINT QUI SEPARE UN REFUS D'UN CHIFFRE FAUX. Le §56 impose
        d'actualiser ; ce lot ne le construit pas. Mesurer sans lui rendrait
        un LRC faux SANS LE DIRE -- exactement le defaut que ce depot
        traque. C2-4 levera ce refus, pas avant.
        """
        with self.assertRaises(RefusMesure) as ctx:
            lrc_initial(3000.0, 0.0, verdict_53_declare=VERDICT_53_ELIGIBLE,
                        financement_significatif=True)
        self.assertEqual(ctx.exception.motif,
                         MOTIF_FINANCEMENT_NON_CONSTRUIT)
        self.assertIn('§56', str(ctx.exception))
        print("    OK M2b : financement significatif -> REFUS, jamais un "
              "LRC non actualise rendu en silence")

    def test_une_duree_nulle_ou_negative_est_refusee(self):
        for duree in (0, -1):
            with self.assertRaises(RefusMesure) as ctx:
                revenue_prorata_temporis(1000.0, duree)
            self.assertEqual(ctx.exception.motif, MOTIF_DUREE_INVALIDE)
        print("    OK M2c : duree <= 0 refusee, jamais de division muette")

    def test_un_montant_negatif_signale_une_convention_divergente(self):
        """Le module pose les signes lui-meme ; un negatif en entree veut
        dire que l'appelant en pose d'autres."""
        with self.assertRaises(RefusMesure) as ctx:
            lrc_initial(-1000.0, 200.0, verdict_53_declare=VERDICT_53_ELIGIBLE)
        self.assertEqual(ctx.exception.motif, MOTIF_MONTANT_NEGATIF)
        print("    OK M2d : montant negatif refuse, convention d'appel "
              "signalee")


class T3_LaFrontiereAvecLeSocle(unittest.TestCase):
    """T3 — ce module ne connaît pas les groupes, et c'est voulu."""

    def test_aucune_dependance_au_socle(self):
        """⚠️ LE SOCLE NE PORTE AUCUN MONTANT, UN TEST L'INTERDIT. La
        reciproque tient ici : la mesure ne prend pas de `Groupe`, elle
        prend des montants nommes. Un import du socle ferait fuir l'unite de
        compte dans le calcul, et le calcul dans l'unite de compte.
        """
        import ast
        import inspect

        from normes.ifrs17.mesure import lrc_paa
        # ⚠️ ON TESTE LES IMPORTS ET LES ANNOTATIONS, PAS LES MENTIONS. La
        # premiere version cherchait `Groupe` dans le SOURCE ENTIER et a
        # echoue le jour ou un commentaire a ecrit « une valeur, jamais un
        # `Groupe` » -- une PHRASE qui dit precisement que la dependance
        # n'existe pas. C'est le defaut que le test voisin
        # `test_le_module_n_importe_AUCUNE_porte` avait deja corrige : un
        # test qui confond un import et une mention echoue pour une raison
        # qui n'interesse personne.
        arbre = ast.parse(inspect.getsource(lrc_paa))
        importes = set()
        for n in ast.walk(arbre):
            if isinstance(n, ast.Import):
                importes |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                importes.add(n.module or '')
        du_socle = {i for i in importes if 'socle' in i}
        self.assertEqual(du_socle, set(), f'imports du socle : {du_socle}')
        # et aucune ANNOTATION ne porte un type du socle
        annotations = {ast.unparse(n.annotation) for n in ast.walk(arbre)
                       if isinstance(n, (ast.AnnAssign, ast.arg))
                       and getattr(n, 'annotation', None)}
        for interdit in ('Groupe', 'CleGroupe', 'Registre'):
            self.assertNotIn(interdit, ' '.join(annotations), interdit)
        print("    OK M3 : aucune dependance au socle — la frontiere tient "
              "dans les deux sens")


if __name__ == '__main__':
    unittest.main()
