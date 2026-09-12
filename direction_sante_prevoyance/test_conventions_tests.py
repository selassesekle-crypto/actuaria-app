"""
Sceau de convention — les tests de la direction doivent rester visibles du lanceur.

POURQUOI CE FICHIER EXISTE
La gate du dépôt lance `unittest discover`, qui ne collecte QUE les sous-classes
de `unittest.TestCase`. Une fonction `test_*` nue, au niveau module, est
parfaitement exécutée par pytest et totalement INVISIBLE pour unittest : le
lanceur rend alors « Ran 0 tests » sans rien signaler d'anormal.

Le 12/09/2026, les 19 fichiers de test de cette direction portaient 132 fonctions
nues et zéro TestCase : pytest en rendait 137 verts, `unittest discover` en voyait
ZÉRO. Aucune garantie locale n'existait donc, alors que tout paraissait vert.

Ce sceau interdit le retour de cette situation. Il échoue si :
  - une fonction `test_*` est définie au niveau module d'un fichier de test ;
  - un fichier de test ne porte aucune classe `TestCase`.

ASSIETTE : les 19 fichiers, pas un seul. Un sceau qui ne lirait qu'un fichier
laisserait passer la régression dans les dix-huit autres.
"""
import ast
import io
import os
import unittest

_RACINE = os.path.dirname(os.path.abspath(__file__))


def _fichiers_de_test():
    """Tous les fichiers de test de la direction, ce fichier-ci excepté."""
    moi = os.path.basename(__file__)
    trouves = []
    for dossier, _, fichiers in os.walk(_RACINE):
        if "__pycache__" in dossier:
            continue
        for f in sorted(fichiers):
            if f.startswith("test_") and f.endswith(".py") and f != moi:
                trouves.append(os.path.join(dossier, f))
    return sorted(trouves)


def _herite_de_testcase(noeud):
    """Vrai si la classe hérite de TestCase, quelle que soit la forme du nom."""
    for base in noeud.bases:
        nom = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
        if nom.endswith("TestCase"):
            return True
    return False


class TestConventionsDesTests(unittest.TestCase):
    """Garde-fou : aucun test ne doit redevenir invisible du lanceur du dépôt."""

    @classmethod
    def setUpClass(cls):
        cls.fichiers = _fichiers_de_test()

    def test_le_perimetre_du_sceau_n_est_pas_vide(self):
        """Un sceau dont l'assiette est vide ne prouve rien : on la mesure."""
        self.assertGreaterEqual(
            len(self.fichiers), 19,
            "Le sceau ne voit que %d fichier(s) de test ; il en attend au moins 19. "
            "Une assiette qui rétrécit fait passer la régression qu'il doit bloquer."
            % len(self.fichiers))

    def test_aucune_fonction_test_nue_au_niveau_module(self):
        """Une fonction `test_*` hors TestCase est invisible d'unittest discover."""
        nues = []
        for chemin in self.fichiers:
            arbre = ast.parse(io.open(chemin, encoding="utf-8").read())
            for noeud in arbre.body:
                if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and noeud.name.startswith("test_"):
                    nues.append("%s:%d %s"
                                % (os.path.relpath(chemin, _RACINE),
                                   noeud.lineno, noeud.name))
        self.assertEqual(
            [], nues,
            "%d fonction(s) de test au niveau module : invisibles d'unittest "
            "discover, donc non couvertes par la gate.\n  %s"
            % (len(nues), "\n  ".join(nues)))

    def test_chaque_fichier_de_test_porte_au_moins_un_testcase(self):
        """Un fichier sans TestCase ne rend aucun test au lanceur du dépôt."""
        sans = []
        for chemin in self.fichiers:
            arbre = ast.parse(io.open(chemin, encoding="utf-8").read())
            if not any(isinstance(n, ast.ClassDef) and _herite_de_testcase(n)
                       for n in arbre.body):
                sans.append(os.path.relpath(chemin, _RACINE))
        self.assertEqual(
            [], sans,
            "%d fichier(s) de test sans aucune classe TestCase :\n  %s"
            % (len(sans), "\n  ".join(sans)))


if __name__ == "__main__":
    unittest.main()
