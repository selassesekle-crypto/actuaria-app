"""
Sceau — l'instrument de preuve du module doit être sensible à ce qu'il scelle.

POURQUOI CE FICHIER EXISTE (D28)
Le hash de session de SP-AUDIT portait sur la liste des agents exécutés, leurs
`audit_id` — qui contiennent un horodatage — et trois chaînes de version. Aucune
valeur de résultat n'y entrait. Mesuré le 12/09/2026 en trompant délibérément
l'instrument : l'empreinte restait **identique** après avoir multiplié le Best
Estimate par 1 000, le SCR par 1 000, mis la PM Rentes et le MCR à zéro, et fait
basculer les sept agents de VERT à ROUGE ; et elle **changeait** quand on
relançait les mêmes chiffres le lendemain.

Un sceau insensible à ce qu'il scelle n'atteste rien. Un sceau qui change sans
qu'aucun chiffre n'ait bougé rend en outre impossible la démonstration qu'un
rapport archivé correspond à ses calculs.

CE QUE CE SCEAU VÉRIFIE
  1. toute falsification d'une grandeur publiée change l'empreinte ;
  2. deux exécutions des mêmes chiffres rendent la MÊME empreinte, malgré des
     `audit_id` différents à chaque passage ;
  3. le périmètre scellé est publié, et il n'est pas vide ;
  4. le registre d'hypothèses trace le chargement RÉELLEMENT appliqué.

La première vérification porte sur cinq falsifications, et non sur une : un
sceau éprouvé par un seul cas ne dit rien de son assiette.
"""
import contextlib
import copy
import io
import unittest

from .reglementation.sp_audit.agent import AgentSPAuditTrail
from .sante.s1_tarification.agent import AgentS1TarificationSante
from .sante.s2_provisionnement.agent import AgentS2ProvissionnementSante
from .sante.s3_reporting.agent import AgentS3ReportingSante
from .services.sp_scellement import CLES_NON_DETERMINISTES, empreinte_resultats


def _chaine_sante():
    with contextlib.redirect_stdout(io.StringIO()):
        s1 = AgentS1TarificationSante(verbose=False).run(
            nb_assures=500, age_moyen=40, contrat="collectif",
            garantie_niveau="confort", chargement_pct=0.18,
            generer_graphiques=False)
        s2 = AgentS2ProvissionnementSante(verbose=False).run(
            result_s1=s1, generer_graphiques=False)
        s3 = AgentS3ReportingSante(verbose=False).run(
            result_s1=s1, result_s2=s2, fonds_propres=5_000_000,
            generer_graphiques=False)
    return {"s1": s1, "s2": s2, "s3": s3}


def _sceller(resultats):
    empreinte, perimetre = empreinte_resultats(
        resultats, date_arrete="2026-12-31", versions={"bcac": "2019"})
    return empreinte, perimetre


class TestLeSceauEstSensibleAuxResultats(unittest.TestCase):
    """D28 — falsifier une grandeur publiée DOIT changer l'empreinte."""

    @classmethod
    def setUpClass(cls):
        cls.base = _chaine_sante()
        cls.reference, cls.perimetre = _sceller(cls.base)

    def _falsifier(self, mutation):
        copie = copy.deepcopy(self.base)
        mutation(copie)
        empreinte, _ = _sceller(copie)
        return empreinte

    def test_le_perimetre_scelle_n_est_pas_vide(self):
        """Un sceau qui ne couvre rien passe tous les tests sans rien prouver."""
        self.assertGreater(
            len(self.perimetre), 50,
            "Le sceau ne couvre que %d champ(s). Avant correction, il n'en "
            "couvrait AUCUN des resultats." % len(self.perimetre))

    def test_falsifier_le_best_estimate_change_l_empreinte(self):
        autre = self._falsifier(
            lambda r: r["s2"].update(be_sante=float(r["s2"].get("be_sante", 1)) * 1000))
        self.assertNotEqual(self.reference, autre,
                            "BE x 1000 laisse l'empreinte inchangee.")

    def test_falsifier_le_scr_change_l_empreinte(self):
        autre = self._falsifier(
            lambda r: r["s3"].update(scr_sante=float(r["s3"].get("scr_sante", 1)) * 1000))
        self.assertNotEqual(self.reference, autre,
                            "SCR x 1000 laisse l'empreinte inchangee.")

    def test_mettre_le_mcr_a_zero_change_l_empreinte(self):
        autre = self._falsifier(lambda r: r["s3"].update(mcr_sante=0.0))
        self.assertNotEqual(self.reference, autre,
                            "MCR mis a 0 laisse l'empreinte inchangee.")

    def test_mettre_le_ratio_scr_a_zero_change_l_empreinte(self):
        autre = self._falsifier(lambda r: r["s3"].update(ratio_scr_pct=0.0))
        self.assertNotEqual(self.reference, autre,
                            "Ratio SCR mis a 0 laisse l'empreinte inchangee.")

    def test_basculer_tous_les_rag_change_l_empreinte(self):
        def basculer(r):
            for agent in r.values():
                agent["statut_rag"] = "ROUGE"
        autre = self._falsifier(basculer)
        self.assertNotEqual(self.reference, autre,
                            "Les RAG passes a ROUGE laissent l'empreinte inchangee.")


class TestLeSceauEstStable(unittest.TestCase):
    """D28 — le même calcul doit rendre le même sceau, horodatages compris."""

    def test_deux_executions_des_memes_chiffres_rendent_le_meme_sceau(self):
        base = _chaine_sante()
        premier, _ = _sceller(base)

        # Les audit_id sont regeneres a chaque appel et portent un horodatage :
        # c est exactement ce qui faisait changer l ancien sceau sans raison.
        copie = copy.deepcopy(base)
        for agent in copie.values():
            agent["audit_id"] = "REGENERE_" + str(id(agent))
            agent["duree_sec"] = 999.99
        second, _ = _sceller(copie)

        self.assertEqual(
            premier, second,
            "Le sceau change alors qu'aucun chiffre n'a bouge : seuls les "
            "horodatages et les durees different. Un sceau instable rend "
            "impossible la verification d'un rapport archive.")

    def test_les_cles_non_deterministes_sont_declarees(self):
        """L'exclusion doit être explicite et lisible, jamais implicite."""
        for cle in ("audit_id", "duree_sec"):
            self.assertIn(
                cle, CLES_NON_DETERMINISTES,
                "'%s' varie d'une execution a l'autre : son exclusion doit "
                "etre declaree dans CLES_NON_DETERMINISTES." % cle)


class TestLeRegistreTraceLHypotheseAppliquee(unittest.TestCase):
    """Le registre doit publier le chargement réellement appliqué."""

    def test_le_chargement_publie_est_celui_du_calcul(self):
        with contextlib.redirect_stdout(io.StringIO()):
            s1 = AgentS1TarificationSante(verbose=False).run(
                nb_assures=500, age_moyen=40, contrat="collectif",
                garantie_niveau="confort", chargement_pct=0.18,
                generer_graphiques=False)
            audit = AgentSPAuditTrail(verbose=False).run(
                resultats_agents={"s1": s1}, date_arrete="2026-12-31",
                generer_graphiques=False)

        lignes = [h for h in audit["hypotheses"].get("hypotheses_effectives", [])
                  if "CHARGEMENT" in h.get("id", "")]
        self.assertEqual(1, len(lignes),
                         "Le registre doit porter exactement une ligne de "
                         "chargement, il en porte %d." % len(lignes))
        valeur = lignes[0]["valeur"]
        self.assertTrue(
            valeur.startswith("18.0%"),
            "Le registre publie %r alors que le calcul applique 18,0 %%. "
            "Avant correction il publiait 100,0 %% : il comparait un total de "
            "portefeuille a une prime unitaire." % valeur)

    def test_le_sceau_est_publie_avec_son_perimetre(self):
        with contextlib.redirect_stdout(io.StringIO()):
            s1 = AgentS1TarificationSante(verbose=False).run(
                nb_assures=500, age_moyen=40, contrat="collectif",
                garantie_niveau="confort", chargement_pct=0.18,
                generer_graphiques=False)
            audit = AgentSPAuditTrail(verbose=False).run(
                resultats_agents={"s1": s1}, date_arrete="2026-12-31",
                generer_graphiques=False)

        self.assertTrue(audit.get("hash_session"), "Aucune empreinte publiee.")
        self.assertGreater(
            audit.get("nb_champs_scelles", 0), 0,
            "L'agent publie une empreinte sans dire ce qu'elle couvre. "
            "Un sceau muet sur son perimetre ne vaut guere mieux qu'un sceau vide.")
        self.assertIsInstance(audit.get("perimetre_scelle"), list)


if __name__ == "__main__":
    unittest.main()
