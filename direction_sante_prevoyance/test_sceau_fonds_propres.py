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


class TestAucunCoefficientHorsReglementNeSurvit(unittest.TestCase):
    """⚠️ CE QUE LE LOT 9 AVAIT MANQUÉ, TROUVÉ LE 12/09/2026.

    Le service portait bien l'annexe XIX, et S3 comme P4 l'appelaient. Mais
    `sante/rapport_sante/agent.py` gardait **sa propre paire** 4,53 % / 3,51 %
    et l'utilisait dans sa branche de repli — atteignable : le rapport
    s'exécute sans S3 et publie. Aucune de ces deux valeurs ne figure dans le
    Règlement délégué.

    ⚠️ ET LA PORTÉE SE MESURE. Sur le portefeuille de test, AUCUN euro ne
    bouge : le plancher absolu de 2,5 M€ absorbe tout (MCR linéaire
    34 009 €). Au-delà d'environ **45 M€ de primes**, l'écart devient réel —
    à 50 M€, **259 814 € de MCR sous-estimé** ; à 100 M€, 519 629 €. Le défaut
    est donc LATENT, et ce sceau dit à partir d'où il cesse de l'être.

    Un troisième écart au même endroit : `SCR_SIGMA_RES` valait 0,14, qui est
    l'écart-type du **segment 2, protection du revenu**, appliqué à des FRAIS
    DE SOINS. L'annexe XIV donne pour le segment 1 « Assurance frais médicaux,
    lignes d'activité 1 et 13 » : σ primes 5 %, σ réserves **5,7 %**.
    Vérifié au texte consolidé le 12/09/2026.
    """

    #: Valeurs qui ne figurent nulle part dans le Reglement delegue.
    HORS_REGLEMENT = frozenset({"0.0453", "0.0351", "0.0338", "0.0191",
                                "0.0418", "0.0261"})

    @property
    def racine(self):
        import os
        return os.path.dirname(os.path.abspath(__file__))

    def _source(self, *parties):
        import io as _io
        import os
        return _io.open(os.path.join(self.racine, *parties),
                        encoding="utf-8").read()

    def _fichiers(self, avec_tests=True):
        import os
        for dossier, sous, fichiers in os.walk(self.racine):
            sous[:] = [x for x in sous if x != "__pycache__"]
            for fichier in sorted(fichiers):
                if not fichier.endswith(".py"):
                    continue
                if not avec_tests and fichier.startswith("test_"):
                    continue
                yield os.path.join(dossier, fichier)

    def test_les_coefficients_du_service_sont_ceux_de_l_annexe_xix(self):
        from .services import sp_fonds_propres as fp
        attendu = {"frais_medicaux": (0.047, 0.047),
                   "protection_du_revenu": (0.131, 0.085)}
        for segment, (alpha, beta) in attendu.items():
            with self.subTest(segment=segment):
                c = fp.COEFF_MCR[segment]
                self.assertAlmostEqual(alpha, c["alpha"], places=4)
                self.assertAlmostEqual(beta, c["beta"], places=4)

    def test_aucun_agent_ne_calcule_un_mcr_avec_ses_propres_coefficients(self):
        """Une paire locale UTILISÉE rouvre le défaut en silence.

        Le contrôle distingue la constante POSÉE (documentaire, légitime : elle
        garde trace de ce qui a été corrigé) de la constante LUE, qui agit.
        """
        import ast
        import io as _io
        import os

        fautifs = []
        for chemin in self._fichiers(avec_tests=False):
            arbre = ast.parse(_io.open(chemin, encoding="utf-8").read())
            rel = os.path.relpath(chemin, self.racine).replace("\\", "/")
            posees, lues = {}, set()
            for n in ast.walk(arbre):
                if (isinstance(n, ast.Assign)
                        and isinstance(n.value, ast.Constant)
                        and str(n.value.value) in self.HORS_REGLEMENT):
                    for cible in n.targets:
                        if hasattr(cible, "id"):
                            posees[cible.id] = (str(n.value.value), n.lineno)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    lues.add(n.id)
                if isinstance(n, ast.BinOp):
                    for cote in (n.left, n.right):
                        if (isinstance(cote, ast.Constant)
                                and str(cote.value) in self.HORS_REGLEMENT):
                            fautifs.append(
                                "%s:%d  litteral %s dans un calcul"
                                % (rel, cote.lineno, cote.value))
            for nom, (valeur, ligne) in sorted(posees.items()):
                if nom in lues:
                    fautifs.append("%s:%d  %s = %s, et elle est LUE"
                                   % (rel, ligne, nom, valeur))
        self.assertEqual(
            [], fautifs,
            "Coefficient(s) hors Reglement delegue UTILISE(S) : "
            + " | ".join(fautifs)
            + " -- les facteurs du MCR sont a l'annexe XIX, appelee par "
              "l'art. 250 par. 1 point d).")

    def test_le_sigma_sante_est_celui_des_frais_medicaux(self):
        """Annexe XIV segment 1 : sigma primes 5 %, sigma reserves 5,7 %."""
        import re
        src = self._source("sante", "rapport_sante", "agent.py")
        prem = re.search(r"SCR_SIGMA_PREM\s*=\s*([0-9.]+)", src)
        res = re.search(r"SCR_SIGMA_RES\s*=\s*([0-9.]+)", src)
        self.assertIsNotNone(prem, "SCR_SIGMA_PREM introuvable")
        self.assertIsNotNone(res, "SCR_SIGMA_RES introuvable")
        self.assertAlmostEqual(0.05, float(prem.group(1)), places=4)
        self.assertAlmostEqual(
            0.057, float(res.group(1)), places=4,
            msg="0,14 est le sigma du SEGMENT 2 (protection du revenu). "
                "L'appliquer a des frais de soins surestime le SCR de "
                "reserve d'un facteur 2,46.")

    def test_le_rapport_sante_passe_par_le_service_pour_son_mcr(self):
        src = self._source("sante", "rapport_sante", "agent.py")
        self.assertIn(
            "mcr_lineaire_segment(", src,
            "Le rapport Sante doit prendre ses coefficients au service, qui "
            "publie aussi la reference exacte a porter a cote du chiffre.")
        self.assertIn("frais_medicaux", src)

    def test_aucun_module_ne_cite_l_article_252_pour_des_coefficients(self):
        """L'art. 252 s'intitule « entreprises d'assurance multibranches »
        et ne contient AUCUN coefficient.

        ⚠️ Le contrôle laisse passer la CITATION du défaut corrigé — plusieurs
        modules expliquent l'erreur pour qu'on ne la refasse pas. Ce qui est
        interdit, c'est de présenter l'article 252 comme la SOURCE, sans dire
        qu'il ne l'est pas.
        """
        import io as _io
        import os
        import re

        fautifs = []
        for chemin in self._fichiers():
            src = _io.open(chemin, encoding="utf-8").read()
            rel = os.path.relpath(chemin, self.racine).replace("\\", "/")
            for m in re.finditer(r"[Aa]rt\.?\s*252", src):
                no = src[:m.start()].count("\n") + 1
                ligne = src.splitlines()[no - 1]
                if not re.search(r"coefficient|alpha|beta", ligne, re.I):
                    continue
                # la phrase qui DEMENT l article 252 est legitime
                voisinage = src[max(0, m.start() - 500):m.start() + 500]
                if re.search(r"CORRIG|ne contient AUCUN|aucun coefficient"
                             r"|multibranches|FAUSSE|perime", voisinage, re.I):
                    continue
                fautifs.append("%s:%d  %s" % (rel, no, ligne.strip()[:66]))
        self.assertEqual(
            [], fautifs,
            "L'article 252 presente comme source de coefficients : "
            + " | ".join(fautifs))


if __name__ == "__main__":
    unittest.main()
