"""
Sceau — un document déposé n'affirme pas plus que ce que le code garantit.

CE QUE CE SCEAU DÉFEND (D30, D29, D27)

D30 — UNE TERNAIRE NEUTRALISÉE. Les deux branches de la conditionnelle
finissaient sur la MÊME expression `be_sante * 2` : le test `if not qrt` ne
servait à rien, et les primes IFRS 17 valaient TOUJOURS deux fois le Best
Estimate. Syntaxiquement correct, sémantiquement vide — aucun compilateur ne le
signale, aucune relecture rapide ne le voit. Mesuré : primes réelles
**2 032 614 EUR**, valeur utilisée **1 056 676 EUR** (= 2 × BE). Conséquence
algébrique vérifiée : avec PA = 2 × BE, la **CSM se réduit à BE − RA
exactement** — elle n'est plus une marge, c'est une réécriture du BE.

D29 — LE STATUT D'UNE SECTION DU SFCR était décidé en cherchant la CHAÎNE
« conforme » dans son TEXTE. Une section dont le texte dit « non conforme »
**contient** la sous-chaîne « conforme » et sortait donc… conforme. Le contrôle
lisait la prose, pas le comportement. Mesuré : un SFCR à **ratio de couverture
de 46,7 %**, avec un RAG global ROUGE, gardait un badge ✅ en section E
« Gestion du capital ».

Deux mentions ont été retirées du SFCR généré : « 4 directions · autonomie
absolue », que la mesure contredit, et un **agent logiciel nommé actuaire
désigné** — la fonction actuarielle est exercée par une personne, et un SFCR
qui nomme un programme à cette place expose l'entité.

D27 — l'IBNR prévoyance était fabriqué à **30 % de la PSAP** par un coefficient
littéral sans source, alors que P3 calcule un IBNR par triangle. Trois chiffres
pour la même grandeur coexistaient dans le dépôt.
"""
import contextlib
import io
import unittest

from .prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
from .prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
from .prevoyance.p3_provisionnement.agent import AgentP3ProvissionnementPrevoyance
from .prevoyance.p4_reporting.agent import AgentP4ReportingPrevoyance
from .reglementation.sp_reg1_solvabilite2.agent import _statut_section_sfcr
from .reglementation.sp_reg2_ifrs17.agent import AgentSPReg2IFRS17
from .sante.s1_tarification.agent import AgentS1TarificationSante
from .sante.s2_provisionnement.agent import AgentS2ProvissionnementSante
from .sante.s3_reporting.agent import AgentS3ReportingSante
from .services.sp_contrats import valeur_qrt


def _chaine(fonds_propres=9_000_000.0):
    with contextlib.redirect_stdout(io.StringIO()):
        s1 = AgentS1TarificationSante(verbose=False).run(
            nb_assures=5000, age_moyen=38, contrat="collectif",
            garantie_niveau="confort", chargement_pct=0.18,
            generer_graphiques=False)
        s2 = AgentS2ProvissionnementSante(verbose=False).run(
            result_s1=s1, generer_graphiques=False)
        s3 = AgentS3ReportingSante(verbose=False).run(
            result_s1=s1, result_s2=s2, fonds_propres=fonds_propres,
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
            fonds_propres=fonds_propres, generer_graphiques=False)
    return s3, p4


class TestLesPrimesIfrs17SontDesPrimes(unittest.TestCase):
    """D30 — la CSM ne doit pas se réduire à BE moins RA."""

    @classmethod
    def setUpClass(cls):
        cls.s3, cls.p4 = _chaine()
        with contextlib.redirect_stdout(io.StringIO()):
            cls.src = AgentSPReg2IFRS17(verbose=False)._extraire(
                cls.s3, cls.p4, 0.0)

    def test_les_primes_sante_ne_valent_plus_deux_fois_le_be(self):
        pa = float(self.src["pa_sante"])
        deux_be = 2.0 * float(self.src["be_sante"])
        self.assertNotAlmostEqual(
            deux_be, pa, delta=1.0,
            msg="pa_sante = %.0f, soit exactement 2 x BE. Les deux branches de "
                "la ternaire d'origine finissaient sur la meme expression."
                % pa)

    def test_les_primes_retenues_sont_celles_du_qrt(self):
        attendu, trouvee = valeur_qrt(self.s3.get("qrt_s13"), "R0100", "C0010")
        self.assertTrue(trouvee, "Le QRT S.13 doit porter les primes en R0100.")
        self.assertAlmostEqual(
            float(attendu), float(self.src["pa_sante"]), delta=1.0)

    def test_la_provenance_nomme_l_agent_et_pas_seulement_la_cle(self):
        """Une provenance qui n'identifie pas sa source ne vaut rien.

        Une première version de ce correctif rendait « primes_acquises » sans
        préciser d'où : elle est allée chercher les primes de la PRÉVOYANCE
        pour la branche santé, et l'étiquette ne permettait pas de le voir.
        """
        source = self.src.get("source_pa_sante") or ""
        self.assertTrue(source.startswith("S3."),
                        "La source des primes sante doit nommer S3 ; "
                        "obtenue : %r" % source)
        source_prev = self.src.get("source_pa_prev") or ""
        self.assertTrue(source_prev.startswith("P4."),
                        "La source des primes prevoyance doit nommer P4 ; "
                        "obtenue : %r" % source_prev)


class TestLeStatutSfcrEstCalculeEtNonCherche(unittest.TestCase):
    """D29 — le contrôle lisait la prose, pas le comportement."""

    def test_une_section_disant_non_conforme_ne_sort_pas_conforme(self):
        """« non conforme » CONTIENT « conforme » : le piège d'origine."""
        section = {"code": "E", "titre": "Gestion du capital",
                   "contenu": "La situation est non conforme aux exigences."}
        statut = _statut_section_sfcr(section, conforme_scr=False,
                                      conforme_mcr=False)
        self.assertNotEqual(
            "✅", statut,
            "La section E sort conforme alors que les ratios ne le sont pas.")

    def test_la_section_e_suit_les_ratios_et_non_le_texte(self):
        section = {"code": "E", "titre": "Gestion du capital", "contenu": ""}
        self.assertEqual(
            "✅",
            _statut_section_sfcr(section, conforme_scr=True, conforme_mcr=True))
        self.assertEqual(
            "❌",
            _statut_section_sfcr(section, conforme_scr=False, conforme_mcr=True),
            "Un SCR non couvert doit retirer le badge de la section E — "
            "mesure d'origine : badge conserve a un ratio de 46,7 %.")

    def test_les_sections_descriptives_ne_portent_pas_de_verdict(self):
        for code in ("A", "B", "C", "D"):
            with self.subTest(section=code):
                statut = _statut_section_sfcr(
                    {"code": code, "contenu": "conforme"},
                    conforme_scr=True, conforme_mcr=True)
                self.assertNotEqual(
                    "✅", statut,
                    "Une section descriptive ne porte pas de verdict de "
                    "conformite : l'afficher serait deja une affirmation de "
                    "trop.")

    def test_une_section_sans_code_ne_fait_pas_lever(self):
        self.assertTrue(_statut_section_sfcr({}, True, True))
        self.assertTrue(_statut_section_sfcr(None, True, True))


class TestLIbnrPrevoyanceNEstPlusFabrique(unittest.TestCase):
    """D27 — 30 % de la PSAP, par un coefficient sans source."""

    def test_l_ibnr_publie_dit_d_ou_il_vient(self):
        from .rapport_actuariel.agent import AgentSPRapportActuariel
        s3, p4 = _chaine()
        with contextlib.redirect_stdout(io.StringIO()):
            p1 = AgentP1TarificationPrevoyance(verbose=False).run(
                age=40, salaire_brut=45_000, categorie="employe",
                generer_graphiques=False)
            p2 = AgentP2TablesMorbidite(verbose=False).run(
                result_p1=p1, generer_graphiques=False)
            p3 = AgentP3ProvissionnementPrevoyance(verbose=False).run(
                result_p1=p1, result_p2=p2, generer_graphiques=False)
            src = AgentSPRapportActuariel(verbose=False)._m1_ingestion(
                None, None, s3, p1, p2, p3, p4, None, None, None, None, 0.0)
        source = src.get("source_ibnr_prev") or ""
        self.assertTrue(
            source, "L'IBNR prevoyance doit dire d'ou il vient.")
        # Deux issues admissibles, et une seule inadmissible : un IBNR
        # fabrique a 30 % SANS que rien ne le dise.
        if source.startswith("P3."):
            self.assertGreaterEqual(float(src.get("ibnr_prev", 0)), 0.0)
        else:
            self.assertIn(
                "REPLI", source.upper(),
                "Si l'IBNR ne vient pas de P3, le repli doit se DECLARER ; "
                "source publiee : %r" % source)


if __name__ == "__main__":
    unittest.main()
