"""
Sceau — aucun avis actuariel, aucun statut d'hypothèse, sur une donnée absente.

POURQUOI CE FICHIER EXISTE (D26, D12, D33)
Les règles de statut ne connaissaient que deux états, et toutes les comparaisons
étaient orientées dans le sens où zéro est la meilleure valeur possible.
L'absence tombait donc du côté favorable. Mesuré le 12/09/2026 :

  · `AgentSPRapportActuariel().run()` SANS AUCUNE DONNÉE rendait `success=True`,
    un RAG **VERT**, un avis **FAVORABLE**, trois hypothèses **VALIDÉES sur des
    zéros**, un Word de 37 005 octets et un Excel de 12 281 octets. Rien, dans
    le document, ne disait que le périmètre était vide ;
  · l'hypothèse H1 de P3, non calculable faute de colonnes, sortait
    « VALIDÉE, score 80 » ;
  · l'hypothèse H3 de SP-ALM vérifiait que la duration appartenait à [8, 18]
    APRÈS l'avoir écrêtée à [8, 18] : elle sortait VALIDÉE de i = 0,1 % à 20 %,
    et mesurait son propre écrêtage.

CE QUE CE SCEAU VÉRIFIE, ET LE PIÈGE QU'IL ÉVITE
Les trois premiers tests vérifient que l'absence ne passe plus pour une
validation. Le quatrième est le CONTRE-TEST, et il est le plus important :
une chaîne complète et saine ne doit PAS être dégradée. Sans lui, on fermerait
le défaut en rendant le module gratuitement pessimiste — ce qui reviendrait à
remplacer un verdict faux par un autre.

Ce contre-test a déjà servi : une première version du correctif subordonnait le
contrôle du MCR à `rag == "VERT"`, et faisait passer la chaîne complète de ROUGE
à AMBRE. La mesure l'a montré ; la règle est redevenue inconditionnelle.
"""
import contextlib
import io
import unittest

from .prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
from .prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
from .prevoyance.p3_provisionnement.agent import AgentP3ProvissionnementPrevoyance
from .prevoyance.p4_reporting.agent import AgentP4ReportingPrevoyance
from .rapport_actuariel.agent import AgentSPRapportActuariel
from .reglementation.sp_alm.agent import AgentSPAlm
from .sante.s1_tarification.agent import AgentS1TarificationSante
from .sante.s2_provisionnement.agent import AgentS2ProvissionnementSante
from .sante.s3_reporting.agent import AgentS3ReportingSante
from .services.sp_avis import NON_EMIS, NON_MESUREE


class TestAucunAvisSurUnPerimetreVide(unittest.TestCase):
    """D26 — un rapport sans données ne rend pas d'avis."""

    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            cls.vide = AgentSPRapportActuariel(verbose=False).run()

    def test_le_rag_est_rouge_sur_un_perimetre_vide(self):
        self.assertEqual(
            "ROUGE", self.vide.get("statut_rag"),
            "Sans aucun module, le rapport rend %r. Avant correction il rendait "
            "VERT." % self.vide.get("statut_rag"))

    def test_aucun_avis_n_est_emis_sur_un_perimetre_vide(self):
        self.assertEqual(
            NON_EMIS, self.vide.get("avis_actuariel"),
            "Sans aucun module, l'avis rendu est %r. Un actuaire qui signe "
            "engage sa responsabilite : le module ne doit pas se prononcer a "
            "sa place." % self.vide.get("avis_actuariel"))


class TestUneHypotheseNonTesteeNEstPasValidee(unittest.TestCase):
    """D12 — « non testable » ne doit jamais se lire « VALIDÉE »."""

    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            p1 = AgentP1TarificationPrevoyance(verbose=False).run(
                age=40, salaire_brut=45_000, categorie="employe",
                generer_graphiques=False)
            p2 = AgentP2TablesMorbidite(verbose=False).run(
                result_p1=p1, generer_graphiques=False)
            cls.p3 = AgentP3ProvissionnementPrevoyance(verbose=False).run(
                result_p1=p1, result_p2=p2, generer_graphiques=False)

    def test_les_hypotheses_non_testables_le_disent(self):
        hypotheses = {h["id"]: h for h in self.p3.get("hypotheses", [])}
        self.assertIn("H1", hypotheses, "P3 doit publier H1.")
        for identifiant, hypothese in hypotheses.items():
            message = str(hypothese.get("valeur", ""))
            if "non testable" in message.lower():
                self.assertEqual(
                    NON_MESUREE, hypothese["statut"],
                    "%s se declare non testable dans son message et publie "
                    "pourtant le statut %r." % (identifiant, hypothese["statut"]))

    def test_le_statut_non_mesuree_est_un_etat_distinct(self):
        statuts = {h["statut"] for h in self.p3.get("hypotheses", [])}
        self.assertIn(
            NON_MESUREE, statuts,
            "Sur le triangle synthetique par defaut, H1 n'est pas calculable : "
            "son statut doit etre %r. Statuts obtenus : %s"
            % (NON_MESUREE, sorted(statuts)))


class TestUneHypotheseNeMesurePasSonPropreMecanisme(unittest.TestCase):
    """D33 — H3 de SP-ALM doit pouvoir échouer."""

    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            p1 = AgentP1TarificationPrevoyance(verbose=False).run(
                age=40, salaire_brut=45_000, categorie="employe",
                generer_graphiques=False)
            p2 = AgentP2TablesMorbidite(verbose=False).run(
                result_p1=p1, generer_graphiques=False)
            cls.p3 = AgentP3ProvissionnementPrevoyance(verbose=False).run(
                result_p1=p1, result_p2=p2, generer_graphiques=False)

    def _h3(self, taux):
        with contextlib.redirect_stdout(io.StringIO()):
            alm = AgentSPAlm(verbose=False).run(
                result_p3=self.p3, taux_actu=taux, generer_graphiques=False)
        h3 = [h for h in alm.get("hypotheses", []) if h["id"] == "H3"]
        self.assertEqual(1, len(h3), "SP-ALM doit publier H3.")
        return h3[0], alm.get("passif", {})

    def test_h3_echoue_quand_la_duration_theorique_est_hors_bornes(self):
        """À 0,1 %, la duration théorique vaut ~1 001 ans : H3 doit le dire."""
        h3, passif = self._h3(0.001)
        self.assertTrue(
            passif.get("ecretage_duration_actif"),
            "A un taux de 0,1 %, la duration theorique sort des bornes : "
            "l'ecretage doit etre signale.")
        self.assertNotEqual(
            "VALIDÉE", h3["statut"],
            "H3 valide une duration qu'elle a elle-meme ecretee. Avant "
            "correction, elle sortait VALIDEE de 0,1 %% a 20 %%.")

    def test_h3_reste_validee_quand_la_duration_tombe_vraiment_dans_les_bornes(self):
        """Contre-test : H3 ne doit pas devenir systématiquement rouge."""
        h3, passif = self._h3(0.12)
        self.assertFalse(
            passif.get("ecretage_duration_actif"),
            "A 12 %%, la duration theorique (~9,3 a) est DANS les bornes.")
        self.assertEqual(
            "VALIDÉE", h3["statut"],
            "H3 rejette une duration pourtant conforme : le correctif rendrait "
            "l'hypothese inutile dans l'autre sens.")


class TestLaChaineSaineNEstPasDegradee(unittest.TestCase):
    """CONTRE-TEST — fermer le défaut ne doit pas rendre le module pessimiste."""

    def test_une_chaine_complete_rend_un_avis_fonde_sur_ses_hypotheses(self):
        with contextlib.redirect_stdout(io.StringIO()):
            s1 = AgentS1TarificationSante(verbose=False).run(
                nb_assures=5000, age_moyen=38, contrat="collectif",
                garantie_niveau="confort", chargement_pct=0.18,
                generer_graphiques=False)
            s2 = AgentS2ProvissionnementSante(verbose=False).run(
                result_s1=s1, generer_graphiques=False)
            s3 = AgentS3ReportingSante(verbose=False).run(
                result_s1=s1, result_s2=s2, fonds_propres=50_000_000,
                generer_graphiques=False)
            p1 = AgentP1TarificationPrevoyance(verbose=False).run(
                age=40, salaire_brut=45_000, categorie="employe",
                generer_graphiques=False)
            p2 = AgentP2TablesMorbidite(verbose=False).run(
                result_p1=p1, generer_graphiques=False)
            p3 = AgentP3ProvissionnementPrevoyance(verbose=False).run(
                result_p1=p1, result_p2=p2, generer_graphiques=False)
            p4 = AgentP4ReportingPrevoyance(verbose=False).run(
                result_p1=p1, result_p2=p2, result_p3=p3,
                fonds_propres=50_000_000, generer_graphiques=False)
            plein = AgentSPRapportActuariel(verbose=False).run(
                result_s1=s1, result_s2=s2, result_s3=s3,
                result_p1=p1, result_p2=p2, result_p3=p3, result_p4=p4,
                generer_graphiques=False)

        self.assertEqual(
            ["S1", "S2", "S3", "P1", "P2", "P3", "P4"],
            plein.get("modules_disponibles"),
            "Le peripherique de test doit fournir les sept modules.")
        self.assertNotEqual(
            NON_EMIS, plein.get("avis_actuariel"),
            "Sur une chaine COMPLETE, un avis doit etre emis : le refus de se "
            "prononcer ne vaut que sur une absence de perimetre.")
        # Le verdict lui-meme depend des chiffres et n'a pas a etre fige ici ;
        # ce qui est verifie, c'est qu'un avis EXISTE et qu'il est motive.
        self.assertIn(plein.get("statut_rag"), ("VERT", "AMBRE", "ROUGE"))


if __name__ == "__main__":
    unittest.main()
