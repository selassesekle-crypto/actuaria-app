"""
Sceau — la catégorie socio-professionnelle est comptée une fois, et une seule.

POURQUOI CE FICHIER EXISTE (D01, D03, D04, D36)

D01 — La table BCAC centralisée est indexée `(cadre, non_cadre)` : elle porte
déjà la différenciation CSP. P1 la remultipliait par un facteur fin local, sans
retirer le premier. Mesuré : **+35,0 % (ouvrier), −25,0 % (cadre), −40,0 %
(cadre sup.)**, identique à 30, 40, 50 et 60 ans. La preuve la moins
contestable est l'asymétrie entre voisins : P2, sur la MÊME table, n'applique
pas le facteur.

D36 — `sp_data_builder` mettait la colonne en minuscules puis la comparait à
une table contenant « O », « E », « C », « CS » en MAJUSCULES : **100 % des
lignes d'un portefeuille en codes courts devenaient « employe »**.

D04 — `_get_qx(age)` omettait l'argument `sexe` : tout le portefeuille était
tarifé au taux masculin (+78,8 % à 45 ans).

D03 — la catégorie réelle de chaque assuré était écrasée par la dominante.

L'INVARIANT QUE CE SCEAU DÉFEND
Sur le chemin centralisé, les catégories de RÉFÉRENCE — `employe` pour la
colonne non-cadre, `cadre` pour la colonne cadre — doivent recevoir **exactement
le taux de la table**, sans aucun facteur. C'est la signature du bon comptage :
si l'une d'elles s'en écarte, le groupe est compté deux fois.

Et le contre-test compte autant : sur le chemin de REPLI, où la table locale
n'a qu'une colonne toutes CSP confondues, le facteur plein reste légitime. Le
risque de ce correctif était de corriger le bon chemin et de casser l'autre.
"""
import contextlib
import io
import unittest

from .prevoyance.p1_tarification.agent import (
    FACT_CSP_ITT, AgentP1TarificationPrevoyance,
)
from .services.sp_csp import (
    FACT_GROUPE_CENTRAL, construire_map_csp, facteur_residuel, normaliser_csp,
)
from .services.sp_data_builder import CSP_VALIDES
from .services.sp_tables_actuarielles import get_taux_itt_bcac

CATEGORIES = ("ouvrier", "employe", "cadre", "cadre_sup")


def _tarifer(categorie, age=40.0):
    with contextlib.redirect_stdout(io.StringIO()):
        return AgentP1TarificationPrevoyance(verbose=False).run(
            age=age, salaire_brut=45_000, categorie=categorie,
            generer_graphiques=False)


class TestLaCspNEstComptéeQuUneFois(unittest.TestCase):
    """D01 — les catégories de référence reçoivent le taux de la table, nu."""

    def test_les_categories_de_reference_recoivent_le_taux_de_la_table(self):
        for categorie, colonne in (("employe", "non_cadre"), ("cadre", "cadre")):
            with self.subTest(categorie=categorie):
                sorties = _tarifer(categorie)["sorties_p2"]
                attendu = get_taux_itt_bcac(40, colonne)
                self.assertAlmostEqual(
                    attendu, sorties["taux_itt"], places=4,
                    msg="%s doit recevoir le taux de la colonne %s (%.4f) SANS "
                        "facteur ; il recoit %.4f. Un ecart ici signifie que le "
                        "groupe est compte deux fois."
                        % (categorie, colonne, attendu, sorties["taux_itt"]))

    def test_l_ecart_a_la_table_est_le_facteur_RESIDUEL_et_non_le_facteur_plein(self):
        """La finesse à quatre catégories est conservée, sans recompter le groupe."""
        for categorie in CATEGORIES:
            with self.subTest(categorie=categorie):
                colonne, residuel = facteur_residuel(categorie, FACT_CSP_ITT)
                attendu = get_taux_itt_bcac(40, colonne) * residuel
                obtenu = _tarifer(categorie)["sorties_p2"]["taux_itt"]
                self.assertAlmostEqual(
                    attendu, obtenu, places=4,
                    msg="%s : attendu %.4f (table %s x residuel %.3f), obtenu "
                        "%.4f" % (categorie, attendu, colonne, residuel, obtenu))

    def test_la_hierarchie_entre_categories_est_preservee(self):
        """Corriger le double compte ne doit pas aplatir la tarification."""
        primes = {c: _tarifer(c)["primes_pures"]["itt"] for c in CATEGORIES}
        self.assertGreater(primes["ouvrier"], primes["employe"])
        self.assertGreater(primes["employe"], primes["cadre"])
        self.assertGreater(primes["cadre"], primes["cadre_sup"])

    def test_l_ecart_est_constant_en_relatif_a_tout_age(self):
        """Le comptage est multiplicatif : le rapport à la table ne bouge pas."""
        for age in (30.0, 40.0, 50.0, 60.0):
            with self.subTest(age=age):
                sorties = _tarifer("employe", age=age)["sorties_p2"]
                attendu = get_taux_itt_bcac(age, "non_cadre")
                self.assertAlmostEqual(
                    attendu, sorties["taux_itt"], places=4,
                    msg="A %d ans, employe s'ecarte de la table." % age)


class TestLeCheminDeRepliNEstPasTouche(unittest.TestCase):
    """Contre-test — le facteur plein reste légitime sur une table sans CSP."""

    def test_le_facteur_residuel_vaut_le_facteur_plein_sur_la_reference(self):
        """Sur la colonne non-cadre, `employe` est la référence : résiduel = 1."""
        self.assertEqual(1.00, FACT_GROUPE_CENTRAL["non_cadre"])
        colonne, residuel = facteur_residuel("employe", FACT_CSP_ITT)
        self.assertEqual("non_cadre", colonne)
        self.assertAlmostEqual(1.0, residuel, places=6)

    def test_le_residuel_conserve_l_ecart_interne_au_groupe(self):
        """ouvrier / employe doit rester 1,35 ; cadre_sup / cadre doit valoir 0,80."""
        _, r_ouvrier = facteur_residuel("ouvrier", FACT_CSP_ITT)
        _, r_employe = facteur_residuel("employe", FACT_CSP_ITT)
        _, r_cadre = facteur_residuel("cadre", FACT_CSP_ITT)
        _, r_cadre_sup = facteur_residuel("cadre_sup", FACT_CSP_ITT)
        self.assertAlmostEqual(1.35, r_ouvrier / r_employe, places=6)
        self.assertAlmostEqual(0.80, r_cadre_sup / r_cadre, places=6)


class TestLesCodesCourtsSontReconnus(unittest.TestCase):
    """D36 — un code d'une lettre ne doit plus devenir « employe » en silence."""

    @classmethod
    def setUpClass(cls):
        cls.map_csp = construire_map_csp(CSP_VALIDES)

    def test_les_codes_majuscules_sont_reconnus(self):
        for code, attendu in (("O", "ouvrier"), ("E", "employe"),
                              ("C", "cadre"), ("CS", "cadre_sup")):
            with self.subTest(code=code):
                categorie, reconnue = normaliser_csp(
                    code, self.map_csp, CSP_VALIDES)
                self.assertTrue(
                    reconnue,
                    "Le code %r n'est pas reconnu : avant correction, 100 %% "
                    "d'un portefeuille en codes courts devenait 'employe'." % code)
                self.assertEqual(attendu, categorie)

    def test_la_reconnaissance_est_rendue_et_non_supposee(self):
        """Une valeur inconnue doit se signaler, pas se replier en silence."""
        categorie, reconnue = normaliser_csp(
            "valeur_inconnue", self.map_csp, CSP_VALIDES)
        self.assertEqual("employe", categorie)
        self.assertFalse(
            reconnue,
            "Un repli doit se declarer : sans cela, personne ne peut compter "
            "combien de lignes ont ete repliees.")


class TestLaBaseDeMortaliteEstPubliee(unittest.TestCase):
    """D04 — le tarif ne doit plus être masculin sans le dire."""

    def test_la_base_de_mortalite_accompagne_le_taux(self):
        sorties = _tarifer("employe")["sorties_p2"]
        self.assertIn("base_mortalite", sorties,
                      "La base de mortalite doit voyager avec le taux.")
        self.assertIn("unisexe", sorties["base_mortalite"].lower(),
                      "Le tarif par defaut doit etre unisexe et le declarer ; "
                      "base publiee : %r" % sorties["base_mortalite"])

    def test_le_taux_n_est_plus_le_taux_masculin(self):
        from .services.sp_tables_actuarielles import get_qx_th0002
        sorties = _tarifer("employe")["sorties_p2"]
        q_homme = get_qx_th0002(40, "M")
        q_femme = get_qx_th0002(40, "F")
        self.assertAlmostEqual(
            (q_homme + q_femme) / 2.0, sorties["qx"], places=5,
            msg="qx publie = %.6f ; attendu la moyenne unisexe %.6f. Le taux "
                "masculin seul valait %.6f."
                % (sorties["qx"], (q_homme + q_femme) / 2.0, q_homme))


if __name__ == "__main__":
    unittest.main()
