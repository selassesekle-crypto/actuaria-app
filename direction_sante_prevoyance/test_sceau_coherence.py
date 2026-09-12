"""
Sceau — un contrôle de cohérence n'atteste que si ses deux côtés peuvent
DIVERGER.

CE QUE CE SCEAU DÉFEND (D31)
C2, C3 et C4 de SP-COHÉRENCE comparaient deux LECTURES d'une même valeur.
SP-REG2 lit le BE santé chez S3 puis on le compare à S3 ; SP-REG1 lit le SCR
consolidé chez SP-Coord puis on le compare à SP-Coord.

⚠️ LA MESURE QUI TRANCHE N'EST PAS CELLE DE L'AUDIT, ET C'EST LE POINT.
L'audit avait injecté un écart *entre les deux lectures* et conclu « les trois
contrôles ont mordu, le code du filet est bon ». C'est exact, et cela ne dit
rien de l'assiette : on ne peut pas injecter, en production, un écart entre
deux copies du même objet. La mesure décisive perturbe **le producteur amont**,
une seule fois, et regarde si les deux côtés suivent :

                              AVANT le correctif        APRÈS
  BE santé de S3 × 3      les DEUX côtés -> 412 660     A seul bouge,
                          écart 0,0 %  « ✅ OK »        écart 66,67 % ❌
  BE prévoyance de P4 × 3 les DEUX côtés ->  45 400     A seul bouge,
                          écart 0,0 %  « ✅ OK »        écart 66,67 % ❌
  SCR de SP-Coord × 3     les DEUX côtés -> 338 213     A seul bouge,
                          écart 0,0 %  « ✅ OK »        écart 66,67 % ❌

Un contrôle qui certifie une grandeur multipliée par trois ne surveille pas
cette grandeur. Et SP-COHÉRENCE était le SEUL agent VERT du pipeline : sa
couleur verte était le meilleur argument de fiabilité du module, et elle venait
de ces contrôles-là.

⛔ CE QUE LA CORRECTION NE DONNE PAS, et ce sceau ne le laisse pas croire.
Le second côté est RECOMPOSÉ à partir des composantes de S2 et de P3. C'est un
chemin arithmétique distinct, pas un modèle distinct : une erreur à l'intérieur
du calcul de S2 ou de P3 touche encore les deux côtés. La correction attrape
une transcription fautive, un double compte, une composante oubliée, une
agrégation erronée — tout ce qui se passe ENTRE le calcul et la publication.
`nature_independance` porte cette limite jusque dans le document.

Ce sceau vérifie donc DEUX propriétés, et non trois valeurs :
  1. la perturbation d'un producteur fait DIVERGER les deux côtés ;
  2. un statut « OK » est IMPOSSIBLE quand l'indépendance n'est pas établie.
"""
import copy
import unittest

from .services import sp_reconciliation


class TestUnStatutOkEstImpossibleSansIndependance(unittest.TestCase):
    """La règle centrale, éprouvée sur la fonction elle-même."""

    def test_deux_valeurs_identiques_mais_non_independantes_ne_sont_pas_ok(self):
        ok, etat, ecart, mention = sp_reconciliation.statut_reconciliation(
            137_553.41, 137_553.41, seuil=0.05, independant=False)
        self.assertFalse(
            ok, "Un ecart nul entre deux COPIES n'est pas une concordance.")
        self.assertEqual(sp_reconciliation.NON_INDEPENDANT, etat)
        self.assertIsNone(
            ecart, "Aucun ecart ne doit etre publie : il n'en a pas ete mesure.")
        self.assertTrue(mention, "Le motif doit atteindre le document.")

    def test_deux_valeurs_identiques_et_independantes_sont_ok(self):
        ok, etat, ecart, mention = sp_reconciliation.statut_reconciliation(
            137_553.41, 137_553.41, seuil=0.05, independant=True)
        self.assertTrue(ok)
        self.assertEqual("OK", etat)
        self.assertEqual(0.0, ecart)
        self.assertIn("NON deux modeles distincts", mention,
                      "La nature exacte de l'independance doit etre dite.")

    def test_un_ecart_au_dela_du_seuil_n_est_pas_ok(self):
        ok, etat, ecart, _ = sp_reconciliation.statut_reconciliation(
            100.0, 300.0, seuil=0.05, independant=True)
        self.assertFalse(ok)
        self.assertEqual("ECART", etat)
        self.assertAlmostEqual(2.0, ecart, places=6)

    def test_deux_zeros_ne_concordent_pas(self):
        """Zéro contre zéro est l'absence de mesure, pas une concordance."""
        ok, etat, ecart, _ = sp_reconciliation.statut_reconciliation(
            0.0, 0.0, seuil=0.05, independant=True)
        self.assertFalse(ok)
        self.assertEqual(sp_reconciliation.NON_INDEPENDANT, etat)
        self.assertIsNone(ecart)


class TestLaRecompositionEstUneVraieSomme(unittest.TestCase):
    """Une somme amputée ferait crier le contrôle au lieu de le faire taire."""

    def test_be_sante_somme_ses_deux_composantes(self):
        valeur, detail, complete = sp_reconciliation.recomposer_be_sante(
            {"psap_dossiers": 82_498.61, "psap_ibnr": 55_054.80})
        self.assertAlmostEqual(137_553.41, valeur, places=2)
        self.assertTrue(complete)
        self.assertIn("psap_dossiers", detail)
        self.assertIn("psap_ibnr", detail)

    def test_une_composante_absente_rend_la_recomposition_incomplete(self):
        valeur, detail, complete = sp_reconciliation.recomposer_be_sante(
            {"psap_dossiers": 82_498.61})
        self.assertFalse(
            complete,
            "Une somme amputee ressemblerait a un ecart reel : elle doit "
            "rendre le controle NON INDEPENDANT, pas le faire crier.")
        self.assertIn("psap_ibnr", detail)

    def test_be_prevoyance_somme_ses_trois_composantes(self):
        valeur, _, complete = sp_reconciliation.recomposer_be_prevoyance(
            {"psap_ip": 13_500.0, "pm_rentes_ip": 1_460.27, "be_itt": 173.16})
        self.assertAlmostEqual(15_133.43, valeur, places=2)
        self.assertTrue(complete)

    def test_le_scr_consolide_est_refait_par_la_formule_de_l_annexe_iv(self):
        """rho = 0,25 — annexe IV du RD (UE) 2015/35."""
        valeur, detail, complete = sp_reconciliation.recomposer_scr_consolide(
            100.0, 100.0)
        # racine(10 000 + 10 000 + 2 x 0,25 x 10 000) = racine(25 000) = 158,11
        self.assertAlmostEqual(158.1139, valeur, places=3)
        self.assertTrue(complete)
        self.assertIn("0.25", detail)

    def test_un_scr_de_branche_manquant_interdit_de_refaire_l_agregation(self):
        valeur, detail, complete = sp_reconciliation.recomposer_scr_consolide(
            100.0, 0.0)
        self.assertFalse(complete)
        self.assertEqual(0.0, valeur)
        self.assertIn("indisponibles", detail)


class TestLesDeuxCotesDivergentQuandUnProducteurEstPerturbe(unittest.TestCase):
    """LE test du lot : on perturbe, et le contrôle doit mordre.

    Ce n'est pas une vérification de valeurs, c'est une vérification de
    PROPRIÉTÉ — celle que les trois contrôles n'avaient pas.
    """

    @classmethod
    def setUpClass(cls):
        import contextlib
        import io as _io

        from .coordination.sp_coord.agent import AgentSPCoord
        from .prevoyance.p1_tarification.agent import (
            AgentP1TarificationPrevoyance)
        from .prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
        from .prevoyance.p3_provisionnement.agent import (
            AgentP3ProvissionnementPrevoyance)
        from .prevoyance.p4_reporting.agent import AgentP4ReportingPrevoyance
        from .sante.s1_tarification.agent import AgentS1TarificationSante
        from .sante.s2_provisionnement.agent import AgentS2ProvissionnementSante
        from .sante.s3_reporting.agent import AgentS3ReportingSante

        with contextlib.redirect_stdout(_io.StringIO()):
            r1 = AgentP1TarificationPrevoyance(verbose=False).run(
                age=40, salaire_brut=45_000, categorie="employe",
                generer_graphiques=False)
            r2 = AgentP2TablesMorbidite(verbose=False).run(
                result_p1=r1, generer_graphiques=False)
            cls.r3 = AgentP3ProvissionnementPrevoyance(verbose=False).run(
                result_p1=r1, result_p2=r2, generer_graphiques=False)
            cls.r4 = AgentP4ReportingPrevoyance(verbose=False).run(
                result_p1=r1, result_p2=r2, result_p3=cls.r3,
                fonds_propres=5_000_000, generer_graphiques=False)
            s1 = AgentS1TarificationSante(verbose=False).run(
                generer_graphiques=False)
            cls.s2 = AgentS2ProvissionnementSante(verbose=False).run(
                result_s1=s1, generer_graphiques=False)
            cls.s3 = AgentS3ReportingSante(verbose=False).run(
                result_s1=s1, result_s2=cls.s2, fonds_propres=5_000_000,
                generer_graphiques=False)
            cls.coord = AgentSPCoord(verbose=False).run(
                result_s3=cls.s3, result_p4=cls.r4, fonds_propres=5_000_000,
                generer_graphiques=False)

    def _coherence(self, s3=None, r4=None, coord=None):
        import contextlib
        import io as _io

        from .reglementation.sp_coherence.agent import AgentSPCoherence

        with contextlib.redirect_stdout(_io.StringIO()):
            resultat = AgentSPCoherence(verbose=False).run(
                result_s2=self.s2, result_s3=s3 or self.s3,
                result_p3=self.r3, result_p4=r4 or self.r4,
                result_coord=coord or self.coord, generer_graphiques=False)
        return {c["id"]: c for c in resultat["controles"]}

    def test_c2_mord_quand_le_be_sante_publie_est_multiplie_par_trois(self):
        sain = self._coherence()["C2"]
        self.assertTrue(sain["ok"], "L'etat nominal doit concorder : %s"
                        % sain["detail"])
        self.assertTrue(sain["independant"])

        s3 = copy.deepcopy(self.s3)
        s3["be_sante"] = s3["be_sante"] * 3
        perturbe = self._coherence(s3=s3)["C2"]
        self.assertFalse(
            perturbe["ok"],
            "Le BE sante publie a triple et C2 dit encore OK : les deux cotes "
            "viennent de la meme source. detail=%s" % perturbe["detail"])
        self.assertNotEqual(
            sain["valeur_b"], 0,
            "Le second cote doit etre recompose, pas nul.")
        self.assertEqual(
            sain["valeur_b"], perturbe["valeur_b"],
            "Le second cote ne doit PAS suivre la perturbation : c'est tout "
            "ce qui distingue un controle d'une tautologie.")

    def test_c3_mord_quand_le_be_prevoyance_publie_est_multiplie_par_trois(self):
        sain = self._coherence()["C3"]
        self.assertTrue(sain["ok"], sain["detail"])

        r4 = copy.deepcopy(self.r4)
        r4["be_prevoyance"] = r4["be_prevoyance"] * 3
        perturbe = self._coherence(r4=r4)["C3"]
        self.assertFalse(perturbe["ok"], perturbe["detail"])
        self.assertEqual(sain["valeur_b"], perturbe["valeur_b"])

    def test_c4_mord_quand_le_scr_consolide_publie_est_multiplie_par_trois(self):
        sain = self._coherence()["C4"]
        self.assertTrue(sain["ok"], sain["detail"])

        coord = copy.deepcopy(self.coord)
        coord["scr_consolide"] = coord["scr_consolide"] * 3
        perturbe = self._coherence(coord=coord)["C4"]
        self.assertFalse(perturbe["ok"], perturbe["detail"])
        self.assertEqual(sain["valeur_b"], perturbe["valeur_b"])

    def test_les_trois_controles_declarent_la_nature_de_leur_independance(self):
        """La limite doit atteindre le document, pas rester dans le code."""
        controles = self._coherence()
        for cle in ("C2", "C3", "C4"):
            with self.subTest(controle=cle):
                c = controles[cle]
                self.assertIn("independant", c)
                self.assertIn(
                    "NON deux modeles distincts", c["nature_independance"],
                    "%s doit dire que son independance est ARITHMETIQUE et "
                    "non de modele." % cle)

    def test_un_controle_prive_de_son_second_cote_ne_dit_pas_OK(self):
        """Sans les composantes, le contrôle doit s'avouer non indépendant."""
        import contextlib
        import io as _io

        from .reglementation.sp_coherence.agent import AgentSPCoherence

        s2_ampute = copy.deepcopy(self.s2)
        s2_ampute.pop("psap_dossiers", None)
        s2_ampute.pop("psap_ibnr", None)
        with contextlib.redirect_stdout(_io.StringIO()):
            resultat = AgentSPCoherence(verbose=False).run(
                result_s2=s2_ampute, result_s3=self.s3, result_p3=self.r3,
                result_p4=self.r4, result_coord=self.coord,
                generer_graphiques=False)
        c2 = {c["id"]: c for c in resultat["controles"]}["C2"]
        self.assertFalse(
            c2["ok"],
            "Sans second cote, C2 ne doit pas certifier : %s" % c2["detail"])
        self.assertFalse(c2["independant"])
        self.assertIn("NON INDÉPENDANT", c2["statut"])


if __name__ == "__main__":
    unittest.main()
