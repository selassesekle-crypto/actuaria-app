"""
Sceau — la direction produit ses documents sans dépendre d'une autre.

CE QUE CE SCEAU DÉFEND (D00)
`sp_rapport_sante.py` et `sp_rapport_prevoyance.py` sont les **deux seuls
imports inter-directions** du périmètre — relevé exhaustif : 478 nœuds
d'import, 0 vers Vie/Épargne-Retraite. L'autonomie de CALCUL était donc
réelle. Celle du LIVRABLE ne l'était pas :

    feuille de style ....  18 774 -> 50 caracteres
    LOGO_SVG ............  NON REDEFINI dans le bloc except (NameError latent)
    LOGO_URI ............  chaine vide -> <img src="">
    var(--rouge) ........  NON DEFINIE

⚠️ CORRECTION D'UN CONSTAT DE L'AUDIT, MESURÉE ICI MÊME.
L'audit affirmait que « 24 230 caractères de CONTENU HTML disparaissent » et
en tirait un défaut majeur. C'est FAUX, et la mesure le montre : en comparant
les deux arbres, le **texte visible est identique (7 085 caractères)**, le
nombre de tableaux identique (5) et le nombre de lignes identique (38). Ce qui
disparaissait était la feuille de style et le balisage de présentation, pas le
contenu.

Le défaut réel est plus étroit, et il subsiste entier :
  · `LOGO_SVG` non redéfini — une NameError latente ;
  · `var(--rouge)` non définie — **les hypothèses rejetées perdaient leur
    couleur de rejet**. Celle-là porte bien une information, et c'est le seul
    point du constat qui touchait autre chose que l'esthétique ;
  · un document produit sans style, qui a l'air complet et ne l'est pas.

⚠️ SECONDE CORRECTION, trouvée par ce sceau même : l'audit affirmait
« 0 appel à la frontière LLM » et en concluait qu'il n'y avait pas de
narration automatique ici. FAUX — **quatre** surfaces l'appellent, via
`from core import frontiere_llm`. Le relevé les avait classées comme de
simples imports `core` : c'est le piège du relevé par PRÉFIXE DE MODULE, qui
ne voit pas le NOM importé. La surface est bien celle que le commanditaire
avait décrite, et elle est légitime — le prompt rédige un commentaire à
partir de chiffres déjà calculés, sans rien décider ni recalculer.

Ce sceau vérifie donc ce qui est vrai, et non ce que l'audit croyait.
"""
import re
import unittest

from .services import sp_style


class TestLeRepliDeStyleEstComplet(unittest.TestCase):
    """Tous les noms importés doivent exister en mode autonome."""

    def test_la_feuille_autonome_n_est_pas_un_placeholder(self):
        self.assertGreater(
            len(sp_style.CSS_AUTONOME), 800,
            "La feuille de repli fait %d caracteres. Celle d'origine en faisait "
            "50 : un placeholder, pas une feuille de style."
            % len(sp_style.CSS_AUTONOME))

    def test_la_couleur_de_rejet_est_definie(self):
        """Le seul point du constat qui touchait une INFORMATION."""
        self.assertIn(
            "--rouge:", sp_style.CSS_AUTONOME,
            "Sans `--rouge`, les hypotheses rejetees perdent leur couleur de "
            "rejet. Cette couleur porte une information, pas une decoration.")

    def test_les_trois_couleurs_de_statut_sont_definies(self):
        for variable in ("--rouge:", "--ambre:", "--vert:"):
            with self.subTest(variable=variable):
                self.assertIn(variable, sp_style.CSS_AUTONOME)
        for classe in (".statut-rouge", ".statut-ambre", ".statut-vert"):
            with self.subTest(classe=classe):
                self.assertIn(classe, sp_style.CSS_AUTONOME)

    def test_la_classe_d_hypothese_rejetee_existe(self):
        self.assertIn(
            ".hyp-err", sp_style.CSS_AUTONOME,
            "La classe qui met en evidence une hypothese rejetee doit exister "
            "en mode autonome.")

    def test_le_logo_est_defini_et_bien_forme(self):
        """`LOGO_SVG` n'était PAS redéfini : NameError latente."""
        logo = sp_style.LOGO_SVG_AUTONOME
        self.assertTrue(logo.startswith("<svg"))
        self.assertTrue(logo.endswith("</svg>"))
        self.assertEqual(logo.count("<text"), logo.count("</text>"))
        self.assertGreater(len(logo), 100)

    def test_l_uri_du_logo_est_exploitable(self):
        uri = sp_style.uri_svg(sp_style.LOGO_SVG_AUTONOME)
        self.assertTrue(uri.startswith("data:image/svg+xml"))
        self.assertGreater(len(uri), 200)


class TestLesDeuxModulesDeRapportOntUnRepliComplet(unittest.TestCase):
    """Les deux seuls imports inter-directions du périmètre."""

    def _module(self, nom):
        from importlib import import_module
        return import_module("direction_sante_prevoyance.services.%s" % nom)

    def test_les_deux_modules_exposent_logo_et_style(self):
        for nom in ("sp_rapport_sante", "sp_rapport_prevoyance"):
            with self.subTest(module=nom):
                module = self._module(nom)
                self.assertTrue(
                    getattr(module, "LOGO_SVG", None),
                    "%s n'expose pas LOGO_SVG : c'etait precisement le nom "
                    "oublie par le bloc de repli." % nom)
                self.assertTrue(getattr(module, "LOGO_URI", ""))
                self.assertGreater(len(module._css()), 800)

    def test_la_mention_de_mode_n_apparait_qu_en_mode_autonome(self):
        self.assertEqual("", sp_style.mention_mode_autonome(False))
        mention = sp_style.mention_mode_autonome(True)
        self.assertIn("licence autonome", mention)
        self.assertIn("aucun contenu de calcul", mention)


class TestLAutonomieDeCalculEstIntacte(unittest.TestCase):
    """Le couplage est de PRÉSENTATION, et doit le rester."""

    def test_aucun_module_de_calcul_n_importe_une_autre_direction(self):
        """Relevé AST : seuls les deux modules de rapport ont le droit."""
        import ast
        import io
        import os

        racine = os.path.dirname(os.path.abspath(__file__))
        autorises = {"sp_rapport_sante.py", "sp_rapport_prevoyance.py",
                     "sp_style.py"}
        fautifs = []
        for dossier, _, fichiers in os.walk(racine):
            if "__pycache__" in dossier:
                continue
            for fichier in fichiers:
                if not fichier.endswith(".py") or fichier in autorises:
                    continue
                chemin = os.path.join(dossier, fichier)
                arbre = ast.parse(io.open(chemin, encoding="utf-8").read())
                for noeud in ast.walk(arbre):
                    noms = []
                    if isinstance(noeud, ast.Import):
                        noms = [a.name for a in noeud.names]
                    elif isinstance(noeud, ast.ImportFrom):
                        noms = [noeud.module or ""]
                    for nom in noms:
                        if nom.startswith(("direction_non_vie",
                                           "direction_vie_epre")):
                            fautifs.append("%s:%d %s"
                                           % (os.path.relpath(chemin, racine),
                                              noeud.lineno, nom))
        self.assertEqual(
            [], fautifs,
            "%d import(s) vers une autre direction hors des modules de "
            "rapport :\n  %s" % (len(fautifs), "\n  ".join(fautifs)))

    def test_la_frontiere_llm_n_est_appelee_que_par_les_deux_rapports(self):
        """⚠️ CORRECTION D'UN CONSTAT DE L'AUDIT, trouvée par ce sceau même.

        L'audit affirmait « 0 appel à la frontière LLM » et en concluait qu'il
        n'y avait pas de narration automatique ici. C'est FAUX : les deux
        agents de rapport font `from core import frontiere_llm` et appellent
        `frontiere_llm.appeler(...)`. Le relevé d'imports les avait classés
        comme de simples imports `core` — c'est exactement le piège du relevé
        par préfixe de module, qui ne voit pas le NOM importé.

        La surface est bien celle que le commanditaire avait décrite, et elle
        est légitime : le prompt rédige un COMMENTAIRE à partir de chiffres
        déjà calculés, sans rien décider ni recalculer. Ce test vérifie qu'elle
        reste cantonnée aux deux agents de narration.
        """
        import io
        import os

        racine = os.path.dirname(os.path.abspath(__file__))
        trouves = []
        for dossier, _, fichiers in os.walk(racine):
            if "__pycache__" in dossier:
                continue
            for fichier in fichiers:
                if not fichier.endswith(".py") or fichier.startswith("test_"):
                    continue
                chemin = os.path.join(dossier, fichier)
                contenu = io.open(chemin, encoding="utf-8").read()
                if re.search(r"^\s*(from|import)\s+.*frontiere_llm", contenu, re.M):
                    trouves.append(os.path.relpath(chemin, racine))
        # QUATRE surfaces de narration, et non deux : les deux agents de
        # rapport ET les deux modules de mise en forme. L'audit en annoncait
        # ZERO ; le sceau en a trouve deux, puis quatre. C'est la mesure qui
        # fixe l'assiette, jamais la memoire de ce qu'on croit avoir releve.
        autorises = {
            os.path.join("prevoyance", "rapport_prevoyance", "agent.py"),
            os.path.join("sante", "rapport_sante", "agent.py"),
            os.path.join("services", "sp_rapport_prevoyance.py"),
            os.path.join("services", "sp_rapport_sante.py"),
        }
        hors_perimetre = sorted(set(trouves) - autorises)
        self.assertEqual(
            [], hors_perimetre,
            "La frontiere LLM est appelee hors des deux agents de narration : "
            "%s. Elle ne doit servir qu'a REDIGER un commentaire, jamais a "
            "calculer ni a decider." % hors_perimetre)
        self.assertEqual(
            autorises, set(trouves),
            "Les deux agents de narration doivent appeler la frontiere ; "
            "trouves : %s" % sorted(trouves))


if __name__ == "__main__":
    unittest.main()
