"""
Sceau — des fonds propres ne se calculent pas, et un MCR ne s'additionne pas.

CE QUE CE SCEAU DÉFEND (D13, D20, D22, D23, D24, D43)

D20 / D13 / D22 — TROIS MONTANTS POUR LA MÊME ENTITÉ, aucun signalé :
    S3 santé       pa x 0,80            ->    379 652 EUR
    P4 prévoyance  max(est, pa x 2,00)  ->    877 105 EUR
    SP-Coord       max(..., BE x 1,50)  ->  3 309 743 EUR
Le consolidé valait **2,63x la somme de ses branches**, et deux de ces montants
figuraient dans le même dépôt réglementaire. Le `max` de SP-Coord **écrasait la
donnée client** dès qu'elle lui était inférieure : un `max` sur une donnée
fournie n'est pas un repli, c'est une substitution.

D23 — le MCR consolidé additionnait deux planchers absolus, alors que le
Règlement délégué (UE) 2015/35 fixe l'ordre : sommer les termes LINÉAIRES
(art. 249), appliquer le corridor 25–45 % du SCR (art. 248 §2), puis le
plancher absolu **une seule fois** (art. 248 §1).

D24 — `pa_sante = qrt_s13["lignes"][-1]` lisait par POSITION. Cela marchait
par accident, la bonne ligne se trouvant être la dernière.

D43 — LE POINT LE PLUS IMPORTANT DE CE FICHIER. Des sentinelles de fonds
propres existaient déjà… **sur S2 et P3, les deux agents où le défaut avait
déjà été corrigé**. Aucune ne couvrait S3, P4 ni SP-Coord, qui fabriquaient
encore. Le filet était posé à côté de la surface. Ce sceau porte sur les
**agents qui publient**, et c'est toute la différence.
"""
import contextlib
import io
import unittest

from .coordination.sp_coord.agent import AgentSPCoord
from .prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
from .prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
from .prevoyance.p3_provisionnement.agent import AgentP3ProvissionnementPrevoyance
from .prevoyance.p4_reporting.agent import AgentP4ReportingPrevoyance
from .sante.s1_tarification.agent import AgentS1TarificationSante
from .sante.s2_provisionnement.agent import AgentS2ProvissionnementSante
from .sante.s3_reporting.agent import AgentS3ReportingSante
from .services.sp_contrats import valeur_qrt
from .services.sp_fonds_propres import (
    AMCR_NON_VIE, COEFF_MCR, mcr_entite, mcr_lineaire_segment,
)


def _chaine(fonds_propres=0.0):
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
        coord = AgentSPCoord(verbose=False).run(
            result_s3=s3, result_p4=p4, fonds_propres=fonds_propres,
            generer_graphiques=False)
    return s3, p4, coord


class TestUneEstimationDeFondsPropresSeDeclare(unittest.TestCase):
    """D20, D13, D22, D43 — la sentinelle porte sur les agents qui PUBLIENT."""

    @classmethod
    def setUpClass(cls):
        cls.sans = _chaine(fonds_propres=0.0)
        cls.avec = _chaine(fonds_propres=9_000_000.0)

    def test_les_trois_agents_declarent_leur_estimation(self):
        for nom, resultat in zip(("S3", "P4", "SP-Coord"), self.sans):
            with self.subTest(agent=nom):
                self.assertTrue(
                    resultat.get("fonds_propres_estimes"),
                    "%s publie des fonds propres sans les declarer comme "
                    "estimes. Avant correction, les trois fabriquaient en "
                    "silence : 379 652, 877 105 et 3 309 743 EUR pour la meme "
                    "entite." % nom)
                mention = resultat.get("fonds_propres_mention") or ""
                self.assertIn(
                    "ESTIMATION", mention.upper(),
                    "%s : la mention doit atteindre le document, pas seulement "
                    "le journal. Mention : %r" % (nom, mention))

    def test_des_fonds_propres_fournis_ne_sont_pas_marques_estimes(self):
        """Contre-test : ne pas rendre le module bavard quand la donnée existe."""
        for nom, resultat in zip(("S3", "P4", "SP-Coord"), self.avec):
            with self.subTest(agent=nom):
                self.assertFalse(
                    resultat.get("fonds_propres_estimes"),
                    "%s marque comme estimes des fonds propres pourtant "
                    "fournis." % nom)
                self.assertFalse(resultat.get("fonds_propres_mention"))

    def test_une_donnee_fournie_n_est_jamais_ecrasee(self):
        """Le `max` de SP-Coord remplaçait une valeur client trop basse."""
        _, _, coord = _chaine(fonds_propres=1_200_000.0)
        self.assertAlmostEqual(
            1_200_000.0, float(coord["fonds_propres"]), delta=1.0,
            msg="Les fonds propres fournis (1 200 000 EUR) sont remplaces par "
                "%.0f EUR. Un `max` sur une donnee fournie n'est pas un repli."
                % float(coord["fonds_propres"]))


class TestLeMcrEstCalculeAuNiveauEntite(unittest.TestCase):
    """D23 — art. 248 §1 et §2, art. 249 du RD (UE) 2015/35."""

    def test_le_plancher_absolu_n_est_applique_qu_une_fois(self):
        somme_naive = 2 * AMCR_NON_VIE
        mcr, contrainte = mcr_entite(
            mcr_lineaire_total=54_284.0 + 38_099.0, scr_consolide=1_400_000.0)
        self.assertAlmostEqual(AMCR_NON_VIE, mcr, delta=1.0)
        self.assertLess(
            mcr, somme_naive,
            "Additionner deux MCR de branche additionne deux fois le plancher "
            "absolu : %.0f au lieu de %.0f." % (somme_naive, mcr))
        self.assertIn("UNE SEULE FOIS", contrainte.upper())

    def test_le_corridor_est_applique_et_nomme(self):
        mcr, contrainte = mcr_entite(9_000_000.0, 16_000_000.0)
        self.assertAlmostEqual(7_200_000.0, mcr, delta=1.0)
        self.assertIn("plafond", contrainte.lower())

    def test_un_mcr_deja_dans_le_corridor_n_est_pas_touche(self):
        """Contre-test : la correction ne doit pas déplacer un MCR correct."""
        mcr, contrainte = mcr_entite(4_000_000.0, 12_000_000.0)
        self.assertAlmostEqual(4_000_000.0, mcr, delta=1.0)
        self.assertEqual("formule lineaire", contrainte)

    def test_l_agent_publie_la_contrainte_qui_a_mordu(self):
        _, _, coord = _chaine(fonds_propres=9_000_000.0)
        self.assertIn("mcr_contrainte", coord)
        self.assertTrue(coord["mcr_contrainte"])


class TestLesCoefficientsMcrViennentDeLAnnexeXix(unittest.TestCase):
    """Annexe XIX du RD (UE) 2015/35, appelée par l'art. 250 §1 point d)."""

    def test_les_coefficients_des_deux_segments_sont_ceux_du_reglement(self):
        self.assertAlmostEqual(0.047, COEFF_MCR["frais_medicaux"]["alpha"])
        self.assertAlmostEqual(0.047, COEFF_MCR["frais_medicaux"]["beta"])
        self.assertAlmostEqual(0.131, COEFF_MCR["protection_du_revenu"]["alpha"])
        self.assertAlmostEqual(0.085, COEFF_MCR["protection_du_revenu"]["beta"])

    def test_alpha_porte_sur_les_provisions_et_beta_sur_les_primes(self):
        """Le Règlement nomme ainsi ; `p4_reporting` les avait à l'envers."""
        terme, reference = mcr_lineaire_segment(
            "protection_du_revenu", provisions_techniques=1_000_000.0,
            primes_emises=0.0)
        self.assertAlmostEqual(131_000.0, terme, delta=1.0)
        self.assertIn("alpha 13.1% sur provisions", reference)

    def test_la_reference_reglementaire_est_publiee_avec_le_terme(self):
        _, reference = mcr_lineaire_segment("frais_medicaux", 0.0, 1_000_000.0)
        self.assertIn("annexe XIX", reference)
        self.assertIn("250", reference)


class TestUneValeurDeQrtSeLitParSaCle(unittest.TestCase):
    """D24 — le rattachement par position rompt sans erreur."""

    def test_ajouter_une_ligne_ne_deplace_pas_la_lecture(self):
        qrt = {"lignes": [
            {"code": "R0100", "libelle": "Primes acquises", "C0010": 2_032_614.0},
        ]}
        avant, _ = valeur_qrt(qrt, "R0100", "C0010")
        qrt["lignes"].append(
            {"code": "R0999", "libelle": "Total", "C0010": 9_999_999.0})
        apres, trouvee = valeur_qrt(qrt, "R0100", "C0010")
        self.assertTrue(trouvee)
        self.assertEqual(
            avant, apres,
            "Une ligne ajoutee deplace la lecture : c'est exactement ce que "
            "faisait `lignes[-1]`.")

    def test_un_code_absent_se_declare_au_lieu_d_inventer_un_zero(self):
        valeur, trouvee = valeur_qrt({"lignes": []}, "R0100", "C0010")
        self.assertIsNone(valeur)
        self.assertFalse(trouvee)

    def test_le_consolide_lit_bien_les_primes_sante(self):
        s3, _, coord = _chaine(fonds_propres=9_000_000.0)
        primes_qrt, trouvee = valeur_qrt(s3.get("qrt_s13"), "R0100", "C0010")
        self.assertTrue(
            trouvee, "Le QRT S.13 doit porter les primes acquises en R0100.")
        self.assertGreater(float(primes_qrt), 0.0)


if __name__ == "__main__":
    unittest.main()
