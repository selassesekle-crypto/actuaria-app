"""
Sceau — un livrable signé doit exister, et la console ne doit pas pouvoir le détruire.

POURQUOI CE FICHIER EXISTE
Deux défauts mesurés le 12/09/2026, tous deux invisibles derrière une suite verte :

D35 — les sept agents de calcul traçaient avec `print()`, et leurs traces portent
      des caractères hors latin-1 (✅, →, ≥, ±). Sur une console `cp1252` — le
      défaut d'un poste Windows français — S1 et P1 levaient `UnicodeEncodeError`,
      l'exception était convertie en `success=False`, et les cinq autres agents
      tombaient en cascade faute d'amont. Mesure : **0 agent sur 7 aboutissait**.
      La suite ne le voyait pas : pytest capture stdout, et les `print`
      n'atteignaient donc jamais la console.

D39 — les modules de rapport lisaient `alm['lcr']` comme un nombre, alors que
      SP-ALM publie un dictionnaire. `float({...})` lève `TypeError`. Résultat,
      **et seulement quand la chaîne allait jusqu'au bout** puisque le crash
      exige que l'ALM soit fournie : HTML de 106 octets, Word de 0 octet.
      Plus la chaîne était complète, moins le document existait.

CE QUE CE SCEAU VÉRIFIE
  1. les sept agents aboutissent sur une console étroite ;
  2. les livrables Prévoyance existent quand l'ALM est fournie ;
  3. le document Word produit s'ouvre réellement et porte du contenu ;
  4. le MCR santé publié ne vaut pas 0 par repli silencieux.

ÉPROUVÉ PAR PLANT : remettre un `print("✅")` brut dans un agent, ou rétablir
`float(alm.get('lcr', 0) or 0)`, fait rougir ce sceau.
"""
import contextlib
import io
import unittest

from .prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
from .prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
from .prevoyance.p3_provisionnement.agent import AgentP3ProvissionnementPrevoyance
from .prevoyance.p4_reporting.agent import AgentP4ReportingPrevoyance
from .reglementation.sp_alm.agent import AgentSPAlm
from .sante.s1_tarification.agent import AgentS1TarificationSante
from .sante.s2_provisionnement.agent import AgentS2ProvissionnementSante
from .sante.s3_reporting.agent import AgentS3ReportingSante
from .services import sp_rapport_prevoyance


class FluxCp1252Strict:
    """Console étroite, fidèle au comportement d'un poste Windows français.

    Installée APRÈS le chargement de la direction, exactement comme le fait la
    capture de pytest : c'est le cas qu'un garde-fou posé à l'import ne couvre
    pas, et c'est pourquoi la protection agit à l'écriture.
    """

    encoding = "cp1252"
    errors = "strict"

    def __init__(self):
        self.caracteres = 0

    def write(self, texte):
        texte.encode("cp1252", errors="strict")   # lève comme la vraie console
        self.caracteres += len(texte)
        return len(texte)

    def flush(self):
        pass

    def isatty(self):
        return False


def _chaine_prevoyance(graphiques=False):
    """P1 → P2 → P3 → P4 → SP-ALM, sur un jeu nominal."""
    p1 = AgentP1TarificationPrevoyance(verbose=False).run(
        age=40, salaire_brut=45_000, categorie="employe",
        generer_graphiques=graphiques)
    p2 = AgentP2TablesMorbidite(verbose=False).run(
        result_p1=p1, generer_graphiques=graphiques)
    p3 = AgentP3ProvissionnementPrevoyance(verbose=False).run(
        result_p1=p1, result_p2=p2, generer_graphiques=graphiques)
    p4 = AgentP4ReportingPrevoyance(verbose=False).run(
        result_p1=p1, result_p2=p2, result_p3=p3,
        fonds_propres=5_000_000, generer_graphiques=graphiques)
    alm = AgentSPAlm(verbose=False).run(
        result_p3=p3, generer_graphiques=graphiques)
    return p1, p2, p3, p4, alm


class TestConsoleEtroiteNeDetruitPasLeCalcul(unittest.TestCase):
    """D35 — sur une console cp1252, les sept agents doivent aboutir."""

    def test_les_sept_agents_aboutissent_sur_console_cp1252(self):
        import sys

        flux = FluxCp1252Strict()
        vrai = sys.stdout
        sys.stdout = flux
        try:
            s1 = AgentS1TarificationSante(verbose=True).run(
                nb_assures=500, age_moyen=40, contrat="collectif",
                garantie_niveau="confort", chargement_pct=0.18,
                generer_graphiques=False)
            s2 = AgentS2ProvissionnementSante(verbose=True).run(
                result_s1=s1, generer_graphiques=False)
            s3 = AgentS3ReportingSante(verbose=True).run(
                result_s1=s1, result_s2=s2, fonds_propres=5_000_000,
                generer_graphiques=False)
            p1 = AgentP1TarificationPrevoyance(verbose=True).run(
                age=40, salaire_brut=45_000, categorie="employe",
                generer_graphiques=False)
            p2 = AgentP2TablesMorbidite(verbose=True).run(
                result_p1=p1, generer_graphiques=False)
            p3 = AgentP3ProvissionnementPrevoyance(verbose=True).run(
                result_p1=p1, result_p2=p2, generer_graphiques=False)
            p4 = AgentP4ReportingPrevoyance(verbose=True).run(
                result_p1=p1, result_p2=p2, result_p3=p3,
                fonds_propres=5_000_000, generer_graphiques=False)
        finally:
            sys.stdout = vrai

        resultats = {"S1": s1, "S2": s2, "S3": s3,
                     "P1": p1, "P2": p2, "P3": p3, "P4": p4}
        echecs = {code: (r.get("erreur") or "sans message")
                  for code, r in resultats.items() if not r.get("success")}
        self.assertEqual(
            {}, echecs,
            "%d agent(s) sur 7 echouent sur une console cp1252 : %s"
            % (len(echecs), echecs))
        self.assertGreater(
            flux.caracteres, 0,
            "Aucune trace n'a ete ecrite : le test ne prouve alors rien sur "
            "l'encodage. Verifier que les agents sont bien en verbose.")


class TestLesLivrablesExistent(unittest.TestCase):
    """D39 — quand la chaine va jusqu'au bout, le document doit exister."""

    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            cls.p1, cls.p2, cls.p3, cls.p4, cls.alm = _chaine_prevoyance()

    def test_le_resultat_alm_est_bien_imbrique(self):
        """La prémisse du défaut : l'ALM publie des sous-dictionnaires."""
        self.assertTrue(self.alm.get("success"), "SP-ALM doit aboutir")
        for cle in ("duration", "bv01", "lcr"):
            self.assertIsInstance(
                self.alm.get(cle), dict,
                "SP-ALM doit publier '%s' comme un dictionnaire : c'est ce que "
                "les modules de rapport doivent savoir lire." % cle)

    def test_le_html_prevoyance_n_est_pas_une_page_d_erreur(self):
        with contextlib.redirect_stdout(io.StringIO()):
            html = sp_rapport_prevoyance.export_html(
                self.p1, self.p2, self.p3, self.p4, result_alm=self.alm)
        self.assertGreater(
            len(html), 10_000,
            "HTML de %d caracteres : le rapport est une page d'erreur, pas un "
            "document. Mesure du defaut d'origine : 106 caracteres."
            % len(html))
        self.assertNotIn(
            "<h1>Erreur", html,
            "Le HTML produit est une page d'erreur : %s" % html[:160])

    def test_le_contexte_de_narration_lit_aussi_l_alm(self):
        """Assiette : `_construire_contexte` n'est traversé par AUCUN autre test.

        La narration est désactivée sans `ANTHROPIC_API_KEY`, donc ce chemin ne
        s'exécute jamais dans la suite. Un plant posé là restait invisible : le
        sceau l'a montré le 12/09/2026, et ce test ferme le trou.
        """
        contexte = sp_rapport_prevoyance._construire_contexte(
            self.p1, self.p2, self.p3, self.p4, self.alm, None, "2026-12-31")
        self.assertIsInstance(contexte, str)
        self.assertGreater(
            len(contexte), 500,
            "Le contexte de narration est trop court pour etre exploitable.")
        self.assertNotIn(
            "Erreur", contexte[:200],
            "Le contexte porte une erreur en tete : %s" % contexte[:160])

    def test_le_word_prevoyance_s_ouvre_et_porte_du_contenu(self):
        with contextlib.redirect_stdout(io.StringIO()):
            blob = sp_rapport_prevoyance.export_word(
                self.p1, self.p2, self.p3, self.p4, result_alm=self.alm)
        self.assertTrue(
            blob, "Word de 0 octet : aucun document signe n'est produit.")
        self.assertGreater(len(blob), 10_000,
                           "Word de %d octets : trop court pour un rapport."
                           % len(blob))

        from docx import Document
        document = Document(io.BytesIO(blob))
        self.assertGreater(
            len(document.paragraphs), 20,
            "Le .docx s'ouvre mais ne porte que %d paragraphes."
            % len(document.paragraphs))
        self.assertGreater(
            len(document.tables), 0,
            "Le .docx ne porte aucun tableau : un rapport prudentiel en a.")


class TestLeMcrSantePublieNestPasUnRepli(unittest.TestCase):
    """D39 — `s3['mcr']` n'existe pas ; le rapport lisait 0 en silence."""

    def test_le_mcr_sante_est_lu_sous_son_vrai_nom(self):
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

        self.assertNotIn(
            "mcr", [c for c in s3 if c == "mcr"],
            "S3 publierait maintenant 'mcr' : verifier que les lecteurs ne "
            "sont pas restes sur l'ancien nom.")
        self.assertIn("mcr_sante", s3,
                      "S3 doit publier son MCR sous le nom 'mcr_sante'.")
        self.assertGreater(
            float(s3["mcr_sante"]), 0.0,
            "Le MCR sante publie vaut 0 : c'est la signature d'un repli "
            "silencieux sur une cle absente.")


if __name__ == "__main__":
    unittest.main()
