"""
Sceau — un seuil réglementaire porte son UNITÉ, et deux agents du même module
ne rendent pas deux verdicts opposés.

CE QUE CE SCEAU DÉFEND (D19, D34, D05)

D19 — `ANI_PANIER_MIN` portait quatre nombres NUS, comparés à une charge EN
EUROS et commentés en POURCENTAGE DE BASE DE REMBOURSEMENT :

    ANI_PANIER_MIN = {"medecine": 30.0,   # >= 100% BR consultations
                      "dentaire": 75.0}   # >= 125% BR soins dentaires
    conforme = charge_mutuelle[poste] >= ANI_PANIER_MIN[poste]

Les deux lectures sont incompatibles. Mesure sur 24 configurations (6 âges ×
4 niveaux de garantie) : **0 CONFORME SUR 24**, le poste médecine sortant à
7,52 € face à un seuil de 30. L'erreur ACCUSAIT À TORT, dans 100 % des cas.

Le panier légal est **hétérogène par nature** — ticket modérateur (un taux),
forfait journalier hospitalier (EUR/jour), 125 % du tarif conventionnel (un
taux), forfait optique (EUR) — et c'est précisément ce que quatre nombres nus
ne pouvaient pas exprimer. Source : art. L911-7 et D911-1 du code de la
Sécurité sociale (décret n° 2014-1025), pris en application de l'ANI du
11 janvier 2013.

D34 — S1 et SP-REG3 portaient chacun SA COPIE de la table, avec les mêmes
valeurs fausses. Deux agents du même module rendaient deux verdicts
réglementaires opposés sur le même portefeuille, le même jour, sur les mêmes
données, et aucun agent ne les rapprochait. Ils appellent désormais la MÊME
fonction : il ne peut plus y avoir deux règles, donc plus deux verdicts.

D05 — `part_patronale = prime_comm * 0.60` et, à côté, la chaîne CONSTANTE
« Part patronale 60 % → Conforme ANI 2013 ✅ ». Jamais calculée, jamais
conditionnée : quelle que soit la répartition réelle du contrat client, le
document publiait « 60 % — conforme ». Et l'affirmation dépassait le texte —
l'art. L911-7 CSS impose 50 % **en frais de santé** ; l'étendre à la
prévoyance est une extension que le texte ne fait pas.

⛔ CE QUE CE SCEAU REFUSE D'EXIGER, ET C'EST DÉLIBÉRÉ.
Il n'exige pas que le panier soit atteint. Mesuré après correction : seul le
niveau `premium` y parvient, à tous les âges — parce que la ligne dentaire
(125 % du tarif) demande un facteur de garantie ≥ 1,33 et que `NIVEAUX_GARANTIE`
plafonne `confort` à 1,00. C'est un constat sur le MODÈLE TARIFAIRE, pas un
défaut de la règle, et le sceau ne le maquille pas en l'assouplissant.
"""
import unittest

from .services import sp_ani


class TestChaqueSeuilPorteSonUniteEtSaBase(unittest.TestCase):
    """Le cœur du correctif : un nombre nu ne peut pas exprimer ce panier."""

    def test_toute_ligne_declare_sa_base_son_unite_et_sa_reference(self):
        for poste, regle in sp_ani.PANIER.items():
            with self.subTest(poste=poste):
                self.assertIn(regle["base"], (
                    "ticket_moderateur", "pct_tarif", "forfait_eur",
                    "non_mesurable"))
                self.assertTrue(regle["unite"])
                self.assertTrue(regle["regle"])
                self.assertIn("D911-1", regle["reference"])

    def test_le_panier_melange_bien_des_taux_et_des_forfaits(self):
        """Si toutes les lignes avaient la même base, le défaut d'origine
        n'aurait pas existé — et ce sceau ne servirait à rien."""
        bases = {r["base"] for r in sp_ani.PANIER.values()}
        self.assertGreaterEqual(
            len(bases), 3,
            "Le panier legal melange taux, forfaits journaliers et forfaits "
            "en euros. Une seule base signifierait qu'on est revenu aux "
            "nombres nus. Bases trouvees : %s" % bases)

    def test_le_seuil_du_ticket_moderateur_se_calcule_et_ne_se_pose_pas(self):
        postes = {"medecine": {"cout_acte": 28.50, "remb_ss": 19.95,
                               "charge_mutuelle": 8.55}}
        verdict = sp_ani.verifier_panier(postes, "collectif")
        d = verdict["detail"]["medecine"]
        # TM = 28,50 - 19,95 = 8,55 : la charge le couvre exactement.
        self.assertAlmostEqual(8.55, d["seuil"], places=2)
        self.assertEqual("CONFORME", d["statut"])

    def test_un_seuil_en_euros_ne_devient_pas_un_taux(self):
        """L'optique EST un forfait en euros — la seule ligne où le nombre
        nu d'origine avait, par accident, la bonne unité."""
        postes = {"optique": {"cout_acte": 320.0, "remb_ss": 0.0,
                              "charge_mutuelle": 99.0}}
        d = sp_ani.verifier_panier(postes, "collectif")["detail"]["optique"]
        self.assertEqual(100.0, d["seuil"])
        self.assertEqual("NON CONFORME", d["statut"])

        postes["optique"]["charge_mutuelle"] = 100.0
        d = sp_ani.verifier_panier(postes, "collectif")["detail"]["optique"]
        self.assertEqual("CONFORME", d["statut"])

    def test_le_dentaire_exige_125_pourcent_du_tarif(self):
        # seuil = 1,25 x 180 - 45 = 180
        postes = {"dentaire": {"cout_acte": 180.0, "remb_ss": 45.0,
                               "charge_mutuelle": 179.0}}
        d = sp_ani.verifier_panier(postes, "collectif")["detail"]["dentaire"]
        self.assertAlmostEqual(180.0, d["seuil"], places=2)
        self.assertEqual("NON CONFORME", d["statut"])


class TestCeQuiNEstPasMesurableNeConclutPas(unittest.TestCase):
    """Inventer une durée de séjour pour pouvoir conclure serait fabriquer
    de l'actuariat — dans l'autre sens, mais de la même façon."""

    def test_le_forfait_journalier_est_declare_non_mesurable(self):
        postes = {"hospitalisation": {"cout_acte": 3500.0, "remb_ss": 2800.0,
                                      "charge_mutuelle": 700.0}}
        d = sp_ani.verifier_panier(postes, "collectif")["detail"]["hospitalisation"]
        self.assertEqual(sp_ani.NON_MESURABLE, d["statut"])
        self.assertIsNone(d["seuil"])
        self.assertIn("PAR JOUR", d["explication"])

    def test_un_poste_non_mesurable_ne_rend_pas_le_contrat_non_conforme(self):
        postes = {
            "medecine": {"cout_acte": 28.5, "remb_ss": 19.95, "charge_mutuelle": 20.0},
            "pharmacie": {"cout_acte": 22.0, "remb_ss": 14.3, "charge_mutuelle": 20.0},
            "dentaire": {"cout_acte": 180.0, "remb_ss": 45.0, "charge_mutuelle": 200.0},
            "optique": {"cout_acte": 320.0, "remb_ss": 0.0, "charge_mutuelle": 150.0},
            "hospitalisation": {"cout_acte": 3500.0, "remb_ss": 2800.0,
                                "charge_mutuelle": 700.0},
        }
        verdict = sp_ani.verifier_panier(postes, "collectif")
        self.assertEqual(sp_ani.CONFORME, verdict["statut"])
        self.assertFalse(
            verdict["complet"],
            "Le verdict doit se declarer INCOMPLET tant qu'un poste n'est "
            "pas mesurable.")
        self.assertIn("hospitalisation", verdict["non_mesurables"])
        self.assertIn("INCOMPLET", verdict["note"])


class TestHorsChampNEstPasConforme(unittest.TestCase):
    """Un contrat non soumis n'a rien satisfait."""

    def test_un_contrat_individuel_est_hors_champ_et_non_conforme(self):
        verdict = sp_ani.verifier_panier({}, "individuel")
        self.assertEqual(sp_ani.HORS_CHAMP, verdict["statut"])
        self.assertIsNone(
            verdict["conforme"],
            "« conforme=True » sur un contrat NON SOUMIS est une affirmation "
            "reglementaire que rien ne garantit.")
        self.assertIn("COLLECTIF", verdict["note"].upper())

    def test_le_financement_patronal_en_prevoyance_est_hors_champ(self):
        """L'art. L911-7 CSS impose 50 % EN FRAIS DE SANTÉ."""
        statut, mention = sp_ani.part_patronale_conforme(0.60, "prevoyance")
        self.assertEqual(sp_ani.HORS_CHAMP, statut)
        self.assertIn("FRAIS DE SANTE", mention)
        self.assertIn("extension", mention.lower())

    def test_le_financement_patronal_en_sante_se_calcule(self):
        for part, attendu in ((0.60, sp_ani.CONFORME),
                              (0.50, sp_ani.CONFORME),
                              (0.49, sp_ani.NON_CONFORME),
                              (0.30, sp_ani.NON_CONFORME)):
            with self.subTest(part=part):
                statut, mention = sp_ani.part_patronale_conforme(
                    part, "frais_de_sante")
                self.assertEqual(attendu, statut)
                self.assertIn("L911-7", mention)


class TestLesDeuxAgentsRendentLeMemeVerdict(unittest.TestCase):
    """D34 — il ne peut plus y avoir deux règles, donc plus deux verdicts."""

    @classmethod
    def setUpClass(cls):
        import contextlib
        import io as _io

        from .reglementation.sp_reg3_ani_100sante.agent import (
            AgentSPReg3ANI100Sante)
        from .sante.s1_tarification.agent import AgentS1TarificationSante

        cls.S1 = AgentS1TarificationSante
        cls.REG3 = AgentSPReg3ANI100Sante
        cls._silence = contextlib.redirect_stdout
        cls._io = _io

    def _couple(self, contrat, niveau, age=40):
        with self._silence(self._io.StringIO()):
            s1 = self.S1(verbose=False).run(
                nb_assures=1000, age_moyen=age, contrat=contrat,
                garantie_niveau=niveau, generer_graphiques=False)
            reg3 = self.REG3(verbose=False).run(
                result_s1=s1, contrat=contrat, generer_graphiques=False)
        return s1, reg3

    def test_les_deux_agents_concordent_sur_toutes_les_configurations(self):
        divergences = []
        for contrat in ("collectif", "individuel"):
            for niveau in ("eco", "confort", "premium"):
                s1, reg3 = self._couple(contrat, niveau)
                a, b = s1["ani_conforme"], reg3["ani_conforme"]
                if a != b:
                    divergences.append(
                        "%s/%s : S1=%r vs SP-REG3=%r" % (contrat, niveau, a, b))
        self.assertEqual(
            [], divergences,
            "Deux agents du meme module rendent des verdicts REGLEMENTAIRES "
            "opposes sur le meme portefeuille :\n  %s"
            % "\n  ".join(divergences))

    def test_les_deux_agents_lisent_la_meme_regle(self):
        """Une copie locale de la table rouvrirait D34 en silence."""
        import io as _io
        import os

        racine = os.path.dirname(os.path.abspath(__file__))
        for rel in (("sante", "s1_tarification", "agent.py"),
                    ("reglementation", "sp_reg3_ani_100sante", "agent.py")):
            with self.subTest(agent=rel[1]):
                src = _io.open(os.path.join(racine, *rel), encoding="utf-8").read()
                self.assertIn(
                    "verifier_panier", src,
                    "%s doit appeler la regle commune." % rel[1])
                for copie in ("ANI_PANIER_MIN = {", "ANI_SEUILS = {"):
                    self.assertNotIn(
                        copie, src,
                        "%s porte de nouveau SA COPIE des seuils : c'est "
                        "exactement D34." % rel[1])

    def test_un_contrat_collectif_recoit_un_verdict_et_l_individuel_non(self):
        s1_c, reg3_c = self._couple("collectif", "premium")
        self.assertIn(s1_c["ani_statut"], ("CONFORME", "NON CONFORME"))
        self.assertIsNotNone(reg3_c["ani_conforme"])

        s1_i, reg3_i = self._couple("individuel", "premium")
        self.assertEqual("HORS CHAMP", s1_i["ani_statut"])
        self.assertIsNone(reg3_i["ani_conforme"])


class TestLaPartPatronaleNEstPlusUnLitteral(unittest.TestCase):
    """D05 — la mention ne bougeait jamais ; c'était le problème."""

    @classmethod
    def setUpClass(cls):
        import contextlib
        import io as _io

        from .prevoyance.p1_tarification.agent import (
            AgentP1TarificationPrevoyance)
        cls.P1 = AgentP1TarificationPrevoyance
        cls._silence = contextlib.redirect_stdout
        cls._io = _io

    def _run(self, **kw):
        with self._silence(self._io.StringIO()):
            return self.P1(verbose=False).run(
                age=40, salaire_brut=45_000, categorie="employe",
                generer_graphiques=False, **kw)

    def test_le_taux_publie_suit_le_taux_demande(self):
        for taux in (0.50, 0.60, 0.75, 1.00):
            with self.subTest(taux=taux):
                r = self._run(part_patronale_pct=taux)
                self.assertAlmostEqual(taux, r["part_patronale_pct"], places=4)
                self.assertAlmostEqual(
                    r["prime_commerciale"] * taux, r["part_patronale"],
                    places=1)

    def test_les_deux_parts_somment_a_la_prime(self):
        r = self._run(part_patronale_pct=0.37)
        self.assertAlmostEqual(
            r["prime_commerciale"],
            r["part_patronale"] + r["part_salariale"], places=2)

    def test_la_mention_ne_certifie_pas_la_prevoyance(self):
        """L'art. L911-7 CSS porte sur les FRAIS DE SANTÉ."""
        r = self._run(part_patronale_pct=0.60)
        self.assertEqual("HORS CHAMP", r["statut_financement_patronal"])
        mention = r["mention_financement_patronal"]
        self.assertIn("FRAIS DE SANTE", mention)
        self.assertNotIn("Conforme ANI", mention)

    def test_la_mention_bouge_quand_la_repartition_bouge(self):
        """C'était le cœur du défaut : la chaîne était constante."""
        mentions = {self._run(part_patronale_pct=t)[
            "mention_financement_patronal"] for t in (0.30, 0.50, 0.80)}
        self.assertEqual(
            3, len(mentions),
            "La mention doit dependre de la repartition reelle ; obtenu "
            "%d mention(s) distincte(s) pour 3 repartitions." % len(mentions))


if __name__ == "__main__":
    unittest.main()
