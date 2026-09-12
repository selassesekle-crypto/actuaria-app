"""
Sceau — les trois arbitrages tranchés par le commanditaire le 12/09/2026.

A3 — LES FONDS PROPRES. Trois agents publiaient un ratio de couverture assis
sur des fonds propres FABRIQUÉS, chacun par sa propre formule : S3 à
379 652 €, P4 à 877 105 €, SP-Coord à 3 309 743 € — pour la même entité, et
aucun signalé comme estimation. Le lot 9 les a rendus VISIBLES. L'arbitrage
va plus loin : **on ne publie pas un ratio de solvabilité dont le numérateur
est inventé.** Sans fonds propres fournis, le ratio vaut `None` — jamais 0,
qui se lirait comme une insuffisance de capital — et le RAG passe ROUGE **en
disant que c'est l'ABSENCE DE DONNÉE qui rougit**.

A4 — LA MORTALITÉ, SUR DEUX AXES. Tarifer et provisionner sont deux choses
différentes : la tarification est UNISEXE (Test-Achats, CJUE 2011), le
provisionnement reste DIFFÉRENCIÉ — interdire le sexe au tarif n'interdit pas
de s'en servir pour évaluer un engagement. Les mettre sur le même
interrupteur aurait été une erreur de conception. Et le réglage se DÉCLARE
dans le document : c'est ce qu'un contrôleur demande à voir écrit.

A1 — LES TABLES, ET CE QUE LA MESURE A CHANGÉ À MA RECOMMANDATION.
J'avais recommandé « une seule source, supprimer les copies ». En mesurant
les trois tables dites « TH 00-02 » aux âges qu'elles ont en commun :

      âge    services   sp_tables_bio    p1        écart max
       25     0,00092      0,00085     0,00073      26,0 %
       45     0,00295      0,00232     0,00298      28,4 %
       65     0,01700      0,01230     0,02380      93,5 %

L'écart CROÎT avec l'âge et `sp_tables_biometriques` est SYSTÉMATIQUEMENT la
plus basse — ce qu'on attend d'une table de population ACTIVE, ce qu'elle dit
être. **Ce ne sont pas trois versions : ce sont trois objets.** Les fusionner
serait fabriquer de l'actuariat ; choisir la bonne exige les publications
certifiées, que je n'ai pas.

Ce qui est donc fait, et qui ferme le défaut réel : chaque table DÉCLARE la
population qu'elle décrit et l'état de sa vérification, et les replis locaux
qui servaient des valeurs différentes **en silence** sont remplacés par une
panne franche. Mieux vaut ne pas tarifer que tarifer sur une table qu'on
croyait être une autre.
"""
import unittest

from .services import sp_fonds_propres as fp
from .services import sp_mortalite as mort
from .services import sp_tables_actuarielles as tab


class TestA3UnRatioNeSAssiedPasSurUneEstimation(unittest.TestCase):

    def test_un_ratio_assis_sur_une_estimation_n_est_pas_publiable(self):
        ratio, publiable, mention = fp.ratio_couverture(
            5_000_000, 1_000_000, fonds_propres_estimes=True)
        self.assertIsNone(
            ratio, "Un ratio estime doit valoir None, JAMAIS 0 : zero se lit "
                   "comme une insuffisance de capital reelle.")
        self.assertFalse(publiable)
        self.assertIn("NON CALCULABLE", mention)

    def test_un_ratio_assis_sur_une_donnee_est_publiable(self):
        ratio, publiable, mention = fp.ratio_couverture(
            5_000_000, 1_000_000, fonds_propres_estimes=False)
        self.assertEqual(500.0, ratio)
        self.assertTrue(publiable)
        self.assertEqual("", mention)

    def test_une_exigence_nulle_ne_produit_pas_de_ratio(self):
        ratio, publiable, mention = fp.ratio_couverture(5_000_000, 0, False)
        self.assertIsNone(ratio)
        self.assertFalse(publiable)
        self.assertIn("NON CALCULABLE", mention)

    def test_un_ratio_absent_ne_franchit_aucun_seuil(self):
        """`None >= 100` leverait ; un repli a 0 mentirait."""
        self.assertFalse(fp.ratio_atteint(None, 100))
        self.assertFalse(fp.ratio_atteint(None, 0))
        self.assertTrue(fp.ratio_atteint(130.0, 130))
        self.assertFalse(fp.ratio_atteint(129.9, 130))

    def test_un_ratio_absent_se_dit_au_lieu_de_s_afficher(self):
        self.assertEqual("NON CALCULABLE", fp.texte_ratio(None))
        self.assertEqual("142.7 %", fp.texte_ratio(142.7))

    def test_le_rouge_par_absence_se_distingue_du_rouge_par_insuffisance(self):
        """La nuance decide de ce que le lecteur va faire."""
        rag, motif = fp.statut_sans_ratio("VERT", ratio_publiable=False)
        self.assertEqual("ROUGE", rag)
        self.assertIn("ABSENCE DE DONNEE", motif)
        self.assertIn("non par insuffisance de capital", motif)

        rag, motif = fp.statut_sans_ratio("VERT", ratio_publiable=True)
        self.assertEqual("VERT", rag)
        self.assertEqual("", motif)


class TestA3LesTroisAgentsRefusentDePublier(unittest.TestCase):
    """La règle vaut sur les trois surfaces, pas sur la fonction seule."""

    @classmethod
    def setUpClass(cls):
        import contextlib
        import io as _io
        import logging

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

        logging.disable(logging.CRITICAL)
        with contextlib.redirect_stdout(_io.StringIO()):
            cls.s1 = AgentS1TarificationSante(verbose=False).run(
                nb_assures=1000, age_moyen=40, contrat="collectif",
                garantie_niveau="premium", generer_graphiques=False)
            cls.s2 = AgentS2ProvissionnementSante(verbose=False).run(
                result_s1=cls.s1, generer_graphiques=False)
            r1 = AgentP1TarificationPrevoyance(verbose=False).run(
                age=40, salaire_brut=45_000, categorie="employe",
                generer_graphiques=False)
            r2 = AgentP2TablesMorbidite(verbose=False).run(
                result_p1=r1, generer_graphiques=False)
            cls.r3 = AgentP3ProvissionnementPrevoyance(verbose=False).run(
                result_p1=r1, result_p2=r2, generer_graphiques=False)
            cls.r1, cls.r2 = r1, r2
        cls.S3, cls.P4, cls.CO = (AgentS3ReportingSante,
                                  AgentP4ReportingPrevoyance, AgentSPCoord)
        cls._silence = contextlib.redirect_stdout
        cls._io = _io

    def _chaine(self, fonds_propres):
        with self._silence(self._io.StringIO()):
            s3 = self.S3(verbose=False).run(
                result_s1=self.s1, result_s2=self.s2,
                fonds_propres=fonds_propres, generer_graphiques=False)
            p4 = self.P4(verbose=False).run(
                result_p1=self.r1, result_p2=self.r2, result_p3=self.r3,
                fonds_propres=fonds_propres, generer_graphiques=False)
            co = self.CO(verbose=False).run(
                result_s3=s3, result_p4=p4, fonds_propres=fonds_propres,
                generer_graphiques=False)
        return {"S3": s3, "P4": p4, "SP-Coord": co}

    def test_avec_fonds_propres_les_trois_publient_un_ratio(self):
        for nom, r in self._chaine(5_000_000.0).items():
            with self.subTest(agent=nom):
                self.assertTrue(r["success"], r.get("erreur"))
                self.assertIsNotNone(
                    r["ratio_scr_pct"],
                    "%s doit publier son ratio quand les fonds propres sont "
                    "fournis." % nom)

    def test_sans_fonds_propres_aucun_des_trois_ne_publie_de_ratio(self):
        for nom, r in self._chaine(0.0).items():
            with self.subTest(agent=nom):
                self.assertTrue(
                    r["success"],
                    "%s doit ABOUTIR sans fonds propres — refuser de publier "
                    "un ratio n'est pas planter : %s" % (nom, r.get("erreur")))
                self.assertIsNone(
                    r["ratio_scr_pct"],
                    "%s publie encore un ratio (%s) assis sur des fonds "
                    "propres estimes." % (nom, r["ratio_scr_pct"]))
                self.assertEqual(
                    "ROUGE", r["statut_rag"],
                    "%s : ne pas pouvoir mesurer sa solvabilite ne doit pas "
                    "sortir VERT." % nom)
                self.assertIn(
                    "ABSENCE DE DONNEE", r.get("motif_rag", ""),
                    "%s rougit sans dire que c'est l'absence de donnee, et "
                    "non une insuffisance de capital." % nom)


class TestA4LaDoctrineDuSexePorteDeuxAxes(unittest.TestCase):

    def test_les_deux_axes_sont_arbitres_et_distincts(self):
        tarif, motif_t = mort.doctrine("tarification")
        prov, motif_p = mort.doctrine("provisionnement")
        self.assertTrue(tarif, "La tarification est UNISEXE (Test-Achats).")
        self.assertFalse(prov, "Le provisionnement reste DIFFERENCIE.")
        self.assertNotEqual(
            tarif, prov,
            "Les deux axes sur le meme interrupteur seraient une erreur de "
            "conception : c'est precisement ce que l'arbitrage separe.")
        self.assertIn("Test-Achats", motif_t)
        self.assertIn("TARIFICATION", motif_p)

    def test_un_axe_non_arbitre_ne_recoit_aucun_defaut(self):
        """⚠️ TROUVE PAR LE PLANT : verifier le TYPE de l exception ne
        suffisait pas. Neutraliser la garde explicite laissait le test VERT,
        parce que l acces au dictionnaire leve KeyError de toute facon -- mais
        avec une cle nue, sans dire quels axes sont arbitres ni pourquoi un
        axe inconnu ne doit pas heriter d un defaut. Le message EST le
        correctif ; on le verifie donc lui."""
        for axe in ("", None, "souscription", "reassurance"):
            with self.subTest(axe=axe):
                with self.assertRaises(KeyError) as capture:
                    mort.doctrine(axe)
                message = str(capture.exception)
                self.assertIn("Axe de doctrine inconnu", message)
                self.assertIn("tarification", message)
                self.assertIn("provisionnement", message)
                self.assertIn("defaut", message)

    def test_la_mention_dit_le_reglage_ET_son_motif(self):
        m = mort.mention_doctrine("tarification")
        self.assertIn("UNISEXE", m)
        self.assertIn("Test-Achats", m)
        m = mort.mention_doctrine("provisionnement")
        self.assertIn("DIFFERENCIEE PAR SEXE", m)

    def test_le_provisionnement_utilise_le_sexe_quand_il_est_connu(self):
        table = {("M", 45): 0.00295, ("F", 45): 0.00165}
        f = lambda age, sexe: table[(sexe, age)]
        taux, base = mort.qx_provisionnement(45, f, "F")
        self.assertAlmostEqual(0.00165, taux, places=6)
        self.assertIn("sexe F", base)

    def test_le_provisionnement_ne_l_invente_pas_quand_il_est_inconnu(self):
        table = {("M", 45): 0.00295, ("F", 45): 0.00165}
        f = lambda age, sexe: table[(sexe, age)]
        taux, base = mort.qx_provisionnement(45, f, None)
        self.assertAlmostEqual(0.0023, taux, places=6)
        self.assertIn("NON RENSEIGNE", base)

    def test_la_doctrine_atteint_le_document(self):
        """Enfouie dans une constante, elle ne vaut rien."""
        import contextlib
        import io as _io
        import logging

        from .prevoyance.p1_tarification.agent import (
            AgentP1TarificationPrevoyance)
        logging.disable(logging.CRITICAL)
        with contextlib.redirect_stdout(_io.StringIO()):
            r = AgentP1TarificationPrevoyance(verbose=False).run(
                age=40, salaire_brut=45_000, categorie="employe",
                generer_graphiques=False)
        self.assertIn("UNISEXE", r["doctrine_sexe"])
        self.assertIn("Test-Achats", r["doctrine_sexe"])
        self.assertTrue(r["base_mortalite"])
        sorties = r["sorties_p2"]
        self.assertTrue(sorties["doctrine_sexe_tarification_unisexe"])
        self.assertFalse(sorties["doctrine_sexe_provisionnement_unisexe"])


class TestA1ChaqueTableDitCeQuElleDecrit(unittest.TestCase):

    def test_toute_table_du_registre_declare_sa_population(self):
        for nom in tab.REGISTRE_TABLES:
            with self.subTest(table=nom):
                f = tab.fiche_table(nom)
                self.assertTrue(f["population"],
                                "%s ne dit pas quelle population elle decrit "
                                "— c'est exactement ce qui a permis a trois "
                                "tables de porter le meme nom." % nom)
                self.assertTrue(f["libelle"])
                self.assertTrue(f["source_declaree"])
                self.assertIn("verifie", f)

    def test_une_table_non_verifiee_le_dit_au_lieu_de_se_taire(self):
        """Une dette déclarée n'est pas une dette cachée."""
        non_verifiees = tab.tables_non_verifiees()
        self.assertTrue(
            non_verifiees,
            "Aucune table n'est marquee non verifiee : soit les publications "
            "certifiees ont ete rapprochees — et alors `millesime` doit etre "
            "renseigne — soit la dette a ete effacee sans etre payee.")
        for nom in non_verifiees:
            with self.subTest(table=nom):
                self.assertTrue(tab.fiche_table(nom)["dette"])

    def test_la_mention_porte_la_population_et_l_etat_de_verification(self):
        m = tab.mention_table("TH0002_QX")
        self.assertIn("population generale", m)
        self.assertIn("MILLESIME NON VERIFIE", m)

    def test_une_table_hors_registre_fait_lever(self):
        with self.assertRaises(KeyError):
            tab.fiche_table("TABLE_INVENTEE")

    def test_aucun_agent_ne_garde_de_table_de_mortalite_locale(self):
        """⚠️ Les copies servaient des valeurs DIFFERENTES sous le meme nom.

        `sp_tables_biometriques` est exclu : il décrit la population ACTIVE,
        c'est un objet distinct et son agent est sa place légitime. Ce test
        interdit les copies chez les CONSOMMATEURS.
        """
        import ast
        import io as _io
        import os
        import re

        racine = os.path.dirname(os.path.abspath(__file__))
        consommateurs = [("prevoyance", "p1_tarification", "agent.py"),
                         ("prevoyance", "p3_provisionnement", "agent.py"),
                         ("sante", "s1_tarification", "agent.py")]
        fautifs = []
        for parties in consommateurs:
            chemin = os.path.join(racine, *parties)
            arbre = ast.parse(_io.open(chemin, encoding="utf-8").read())
            for n in ast.walk(arbre):
                if not (isinstance(n, ast.Assign)
                        and isinstance(n.value, ast.Dict)
                        and len(n.value.keys) >= 5):
                    continue
                for cible in n.targets:
                    nom = getattr(cible, "id", "")
                    if re.search(r"(TH0002|TH_0002|QX_TH|BCAC|TD88|TD_88)",
                                 nom, re.I):
                        fautifs.append("%s:%d %s" % (parties[-2], n.lineno, nom))
        self.assertEqual(
            [], fautifs,
            "Table(s) actuarielle(s) recopiee(s) chez un consommateur : %s. "
            "Les copies divergeaient jusqu'a 93,5 %% sous le meme nom de "
            "source." % fautifs)

    def test_un_repli_muet_ne_peut_plus_servir_une_autre_table(self):
        """Mieux vaut une panne franche qu'un tarif silencieusement faux."""
        import io as _io
        import os

        racine = os.path.dirname(os.path.abspath(__file__))
        for parties in (("prevoyance", "p1_tarification", "agent.py"),
                        ("prevoyance", "p2_tables_morbidite", "agent.py")):
            with self.subTest(agent=parties[-2]):
                src = _io.open(os.path.join(racine, *parties),
                               encoding="utf-8").read()
                self.assertIn(
                    "raise ImportError", src,
                    "%s bascule encore en silence sur une table locale au "
                    "lieu de lever." % parties[-2])
                self.assertIn("_erreur_tables", src)


class TestA3LesDocumentsSORTENTQuandLeRatioNExistePas(unittest.TestCase):
    """⚠️ RÉGRESSION QUE J'AI INTRODUITE ET POUSSÉE, TROUVÉE EN MESURANT.

    L'arbitrage A3 fait valoir `None` au ratio quand les fonds propres ne sont
    pas fournis. Les DEUX rapports signés le relisaient avec `float(...)` et
    `>= SEUIL`, et PLANTAIENT : *float() argument must be a string or a real
    number*. Aucun document produit, sur un message illisible.

    **Mes 319 tests verts ne l'ont pas vu**, parce qu'aucun ne lançait les
    agents de rapport avec `fonds_propres=0`. C'est exactement le motif que ce
    chantier traque depuis le début — une assiette qui ne couvre pas le cas où
    la grandeur MANQUE — et je l'ai reproduit dans mon propre correctif.

    Refuser de publier un chiffre n'est pas planter. Un refus s'explique.
    """

    @classmethod
    def setUpClass(cls):
        import contextlib
        import io as _io
        import logging
        logging.disable(logging.CRITICAL)
        cls._silence = contextlib.redirect_stdout
        cls._io = _io

    def _rapports(self, fonds_propres):
        from .prevoyance.p1_tarification.agent import (
            AgentP1TarificationPrevoyance)
        from .prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
        from .prevoyance.p3_provisionnement.agent import (
            AgentP3ProvissionnementPrevoyance)
        from .prevoyance.p4_reporting.agent import AgentP4ReportingPrevoyance
        from .prevoyance.rapport_prevoyance.agent import AgentRapportPrevoyance
        from .sante.rapport_sante.agent import AgentRapportSante
        from .sante.s1_tarification.agent import AgentS1TarificationSante
        from .sante.s2_provisionnement.agent import AgentS2ProvissionnementSante
        from .sante.s3_reporting.agent import AgentS3ReportingSante

        with self._silence(self._io.StringIO()):
            s1 = AgentS1TarificationSante(verbose=False).run(
                nb_assures=1000, age_moyen=40, contrat="collectif",
                garantie_niveau="premium", generer_graphiques=False)
            s2 = AgentS2ProvissionnementSante(verbose=False).run(
                result_s1=s1, generer_graphiques=False)
            s3 = AgentS3ReportingSante(verbose=False).run(
                result_s1=s1, result_s2=s2, fonds_propres=fonds_propres,
                generer_graphiques=False)
            r1 = AgentP1TarificationPrevoyance(verbose=False).run(
                age=40, salaire_brut=45_000, categorie="employe",
                generer_graphiques=False)
            r2 = AgentP2TablesMorbidite(verbose=False).run(
                result_p1=r1, generer_graphiques=False)
            r3 = AgentP3ProvissionnementPrevoyance(verbose=False).run(
                result_p1=r1, result_p2=r2, generer_graphiques=False)
            r4 = AgentP4ReportingPrevoyance(verbose=False).run(
                result_p1=r1, result_p2=r2, result_p3=r3,
                fonds_propres=fonds_propres, generer_graphiques=False)
            return {
                "rapport Sante": AgentRapportSante(verbose=False).run(
                    result_s1=s1, result_s2=s2, result_s3=s3,
                    generer_graphiques=False),
                "rapport Prevoyance": AgentRapportPrevoyance(
                    verbose=False).run(
                    result_p1=r1, result_p2=r2, result_p3=r3, result_p4=r4,
                    generer_graphiques=False),
            }

    def test_les_deux_rapports_sortent_SANS_fonds_propres(self):
        for nom, r in self._rapports(0.0).items():
            with self.subTest(rapport=nom):
                self.assertTrue(
                    r["success"],
                    "%s PLANTE quand les fonds propres manquent : %s. "
                    "Refuser de publier un ratio n'est pas planter."
                    % (nom, r.get("erreur")))
                self.assertGreater(
                    len(r.get("word_bytes") or b""), 10_000,
                    "%s ne produit plus de Word exploitable." % nom)

    def test_le_document_DIT_que_le_ratio_n_est_pas_calculable(self):
        """Un tiret muet laisserait croire a un defaut d'affichage."""
        import re
        for nom, r in self._rapports(0.0).items():
            with self.subTest(rapport=nom):
                brut = r.get("html_bytes")
                html = (brut.decode("utf-8", "replace")
                        if isinstance(brut, bytes) else str(brut or ""))
                texte = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
                self.assertIn(
                    "NON CALCULABLE", texte,
                    "%s publie un ratio absent SANS dire pourquoi." % nom)

    def test_avec_fonds_propres_les_deux_rapports_publient_un_chiffre(self):
        import re
        for nom, r in self._rapports(5_000_000.0).items():
            with self.subTest(rapport=nom):
                self.assertTrue(r["success"], r.get("erreur"))
                brut = r.get("html_bytes")
                html = (brut.decode("utf-8", "replace")
                        if isinstance(brut, bytes) else str(brut or ""))
                self.assertNotIn(
                    "NON CALCULABLE", re.sub(r"<[^>]+>", " ", html),
                    "%s se declare non calculable alors que les fonds "
                    "propres sont fournis." % nom)


if __name__ == "__main__":
    unittest.main()
