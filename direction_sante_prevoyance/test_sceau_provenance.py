"""
Sceau — une valeur et son étiquette sortent de la même fonction.

C'EST LA CAUSE COMMUNE DE L'AUDIT : vingt-neuf constats sur quarante-quatre
relèvent d'un seul motif — **le nom publié ne suit pas la valeur calculée**.
Le calcul n'est pas toujours faux ; la phrase qui l'accompagne l'est presque
toujours, et c'est elle qui sera lue par le commissaire aux comptes.

CE QUE CE SCEAU DÉFEND (D18, D32, D16, D21)

D18 — S1 cherchait `sinistre_<poste>` au SINGULIER quand `SPDataBuilder`
produit `sinistres_<poste>`. Un `s` d'écart : la recherche échouait en silence,
**5 postes sur 5 venaient de DREES 2023**, et la sortie publiait
`source_donnees = "donnees_reelles_a2"`. La provenance était fixée EN AMONT,
sur la seule présence d'un DataFrame. C'est le défaut le plus coûteux
commercialement : l'argument de vente du module est la tarification sur données
réelles.

D32 — SP-TABLES publiait « TABLE PROPRIÉTAIRE CLIENT » alors que `tables_client`
n'atteint **aucune des cinq méthodes de calcul**. Valeur témoin de 0,950
injectée : la sortie valait 0,066, celle du cas sans client.

D16 / D21 — trois jeux de coefficients de MCR coexistaient, aucun présent au
Règlement, tous sous-estimant le plancher ; plus un commentaire annonçant un
quatrième jeu. Ils viennent désormais tous de l'annexe XIX, par une seule
fonction, et la référence réglementaire voyage avec le chiffre.
"""
import contextlib
import io
import unittest

import numpy as np
import pandas as pd

from .prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
from .prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
from .prevoyance.p3_provisionnement.agent import AgentP3ProvissionnementPrevoyance
from .prevoyance.p4_reporting.agent import AgentP4ReportingPrevoyance
from .reglementation.sp_tables_biometriques.agent import AgentSPTablesBiometriques
from .sante.s1_tarification.agent import COUTS_POSTES_REF, AgentS1TarificationSante
from .services.sp_provenance import colonne_sinistres, source_reellement_retenue


def _portefeuille(postes_fournis=None):
    """Portefeuille client dont on choisit les postes réellement renseignés."""
    n = 400
    donnees = {
        "age": np.full(n, 38.0), "sexe": ["M"] * n,
        "salaire_brut": np.full(n, 35_000.0),
        "categorie": ["employe"] * n, "garanties": ["confort"] * n,
    }
    for poste in (postes_fournis if postes_fournis is not None else COUTS_POSTES_REF):
        donnees["sinistres_%s" % poste] = np.full(n, 250.0)
    return pd.DataFrame(donnees)


def _tarifer(dataframe=None):
    with contextlib.redirect_stdout(io.StringIO()):
        a2 = {"success": True, "dataframe": dataframe} if dataframe is not None else None
        return AgentS1TarificationSante(verbose=False).run(
            result_a2=a2, nb_assures=400, age_moyen=38, contrat="collectif",
            garantie_niveau="confort", chargement_pct=0.18,
            generer_graphiques=False)


class TestLaProvenanceSeDeduitDesPostesAlimentes(unittest.TestCase):
    """D18 — « données réelles » ne doit plus s'écrire sur une table nationale."""

    def test_un_portefeuille_complet_donne_donnees_client(self):
        resultat = _tarifer(_portefeuille())
        self.assertEqual("donnees_client", resultat["source_donnees"])
        sources = {p: v["source"] for p, v in resultat["postes"].items()}
        self.assertTrue(
            all(s == "donnees_client" for s in sources.values()),
            "Postes non alimentes par le client : %s" % sources)

    def test_sans_donnees_la_provenance_ne_ment_pas(self):
        resultat = _tarifer(None)
        self.assertEqual(
            "tables_de_reference", resultat["source_donnees"],
            "Sans donnees client, la sortie annonçait « donnees_reelles_a2 ».")

    def test_le_cas_mixte_est_dicible(self):
        """L'ancienne version ne savait pas exprimer le cas partiel."""
        postes = sorted(COUTS_POSTES_REF)[:2]
        resultat = _tarifer(_portefeuille(postes_fournis=postes))
        self.assertEqual("mixte", resultat["source_donnees"])
        detail = resultat["source_donnees_detail"]
        for poste in postes:
            self.assertIn(poste, detail,
                          "Le detail doit NOMMER les postes venant du client.")

    def test_la_colonne_canonique_est_cherchee_avant_l_ancienne(self):
        self.assertEqual(
            "sinistres_medecine",
            colonne_sinistres(["sinistres_medecine", "sinistre_medecine"],
                              "medecine"))
        self.assertIsNone(colonne_sinistres(["autre"], "medecine"))

    def test_la_provenance_est_toujours_motivee(self):
        for dataframe in (None, _portefeuille()):
            with self.subTest(avec_donnees=dataframe is not None):
                resultat = _tarifer(dataframe)
                self.assertTrue(
                    resultat.get("source_donnees_detail"),
                    "Une provenance sans motif ne se verifie pas.")


class TestUneEtiquetteNeSurvitPasAUneLectureQuiNAPasEuLieu(unittest.TestCase):
    """D32 — l'étiquette annonçait la table du client sans l'avoir lue."""

    def _tables(self, tables_client=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return AgentSPTablesBiometriques(verbose=False).run(
                tables_client=tables_client, generer_graphiques=False)

    def test_des_tables_fournies_et_non_exploitees_le_disent(self):
        resultat = self._tables({"incidence_itt": {"table": {40: 0.950}}})
        self.assertTrue(resultat.get("tables_client_fournies"))
        self.assertFalse(
            resultat.get("tables_client_exploitees"),
            "Si les tables client sont reellement exploitees, ce sceau doit "
            "etre mis a jour — et l'etiquette avec.")
        self.assertIn(
            "NON EXPLOITEES", resultat["source_tables"].upper(),
            "L'etiquette doit dire que les tables fournies n'ont pas servi ; "
            "obtenue : %r" % resultat["source_tables"])

    def test_la_valeur_ne_change_pas_quand_la_table_client_n_est_pas_lue(self):
        """La preuve du défaut : la valeur témoin 0,950 n'atteignait rien."""
        sans = self._tables(None)
        avec = self._tables({"incidence_itt": {"table": {40: 0.950}}})
        self.assertEqual(
            sans.get("taux_itt"), avec.get("taux_itt"),
            "Si la valeur change, les tables client sont exploitees et "
            "l'etiquette doit le dire.")


class TestLesCoefficientsMcrViennentTousDeLaMemeSource(unittest.TestCase):
    """D16, D21 — trois jeux coexistaient, aucun présent au Règlement."""

    def test_p4_publie_sa_reference_reglementaire(self):
        with contextlib.redirect_stdout(io.StringIO()):
            p1 = AgentP1TarificationPrevoyance(verbose=False).run(
                age=40, salaire_brut=45_000, categorie="employe",
                generer_graphiques=False)
            p2 = AgentP2TablesMorbidite(verbose=False).run(
                result_p1=p1, generer_graphiques=False)
            p3 = AgentP3ProvissionnementPrevoyance(verbose=False).run(
                result_p1=p1, result_p2=p2, generer_graphiques=False)
            p4 = AgentP4ReportingPrevoyance(verbose=False).run(
                result_p1=p1, result_p2=p2, result_p3=p3,
                fonds_propres=5_000_000, generer_graphiques=False)
        reference = p4.get("mcr_reference") or ""
        self.assertIn("annexe XIX", reference,
                      "Le MCR doit citer sa vraie source, et non l'art. 252 "
                      "qui ne contient aucun coefficient. Obtenu : %r" % reference)
        self.assertIn("protection du revenu", reference.lower())

    def test_aucun_coefficient_mcr_ne_subsiste_hors_du_reglement(self):
        """Les COEFFICIENTS viennent d'sp_fonds_propres ; le PLANCHER reste local.

        ⚠️ Une première version de ce test interdisait toute constante
        `MCR_*`, et accusait `MCR_PLANCHER_ABS` — qui est parfaitement
        légitime. Un sceau dont l'assiette est trop large n'est pas plus sûr :
        il accuse à tort, et on finit par le désactiver.
        """
        from .prevoyance import p4_reporting
        from .sante import s3_reporting
        prefixes_coefficients = ("MCR_ALPHA", "MCR_BETA", "MCR_COEFF")
        for module in (p4_reporting.agent, s3_reporting.agent):
            with self.subTest(module=module.__name__):
                noms = [n for n in dir(module)
                        if n.startswith(prefixes_coefficients)
                        and not n.endswith("_AVANT")]
                self.assertEqual(
                    [], noms,
                    "Coefficients MCR encore definis dans %s : %s. Ils doivent "
                    "venir de l'annexe XIX via sp_fonds_propres."
                    % (module.__name__, noms))


class TestLaFonctionDeProvenanceEstFidele(unittest.TestCase):
    """Le cœur du correctif, testé isolément."""

    def test_aucun_poste_client_donne_tables_de_reference(self):
        source, detail = source_reellement_retenue(
            {"a": {"source": "DREES_2023"}, "b": {"source": "DREES_2023"}})
        self.assertEqual("tables_de_reference", source)
        self.assertIn("Aucun des 2", detail)

    def test_tous_les_postes_client_donnent_donnees_client(self):
        source, _ = source_reellement_retenue(
            {"a": {"source": "donnees_client"}, "b": {"source": "donnees_client"}})
        self.assertEqual("donnees_client", source)

    def test_un_seul_poste_client_donne_mixte(self):
        source, detail = source_reellement_retenue(
            {"a": {"source": "donnees_client"}, "b": {"source": "DREES_2023"}})
        self.assertEqual("mixte", source)
        self.assertIn("1 poste(s) sur 2", detail)


if __name__ == "__main__":
    unittest.main()
