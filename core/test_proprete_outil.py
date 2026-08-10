"""Tests — l'outil de mesure de propreté garde ses trois désamorçages.

⚠️ GATE : `py -m unittest discover -s core -t .` — voir test_imports_app.py,
qui explique pourquoi les tests de ce qui vit hors des directions atterrissent
ici : `scripts/` ne porte aucun test et aucune gate ne l'y découvrirait.

POURQUOI CES TESTS EXISTENT. `scripts/proprete.py` ne calcule rien qui entre
dans un rapport : c'est un INSTRUMENT. Un instrument faux est pire qu'aucun,
parce qu'on le croit. Trois pièges d'outillage ont faussé cette mesure au
moins une fois chacun, et l'outil les désamorce — mais rien n'empêcherait
quelqu'un de « simplifier » l'un des trois et de rendre la mesure muette :

  · écrire la référence dans un fichier temporaire hors du dépôt — ruff n'y
    résout pas la même configuration, et les comptes n'ont plus de sens ;
  · nommer le témoin autrement — vulture cesse alors de taire les méthodes
    `test_*`, et affiche 97 signalements là où il en tient 23 ;
  · appeler `ruff --fix` — il corrige des défauts ANTÉRIEURS au lot, deux
    fois douze hunks hors périmètre dans la même journée.
"""
import ast
import os
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTIL = os.path.join(RACINE, 'scripts', 'proprete.py')


def _source():
    with open(OUTIL, encoding='utf-8') as f:
        return f.read()


class T1_LesTroisDesamorcages(unittest.TestCase):

    def test_la_reference_ruff_passe_par_le_MEME_chemin(self):
        """⚠️ PIÈGE 1. Une référence hors du dépôt ne résout pas la même
        configuration ruff : la comparaison devient un chiffre contre un
        autre chiffre, sans rapport entre eux."""
        src = _source()
        self.assertIn('--stdin-filename', src)
        self.assertNotIn('tempfile', src,
                         'la référence repasse par un fichier temporaire')
        print("    OK 1 : la reference ruff passe par --stdin-filename")

    def test_le_temoin_vulture_garde_le_prefixe_du_nom(self):
        """⚠️ PIÈGE 2. Vulture tait les méthodes `test_*` selon le NOM DU
        FICHIER. Un témoin mal nommé affichait 97 au lieu de 23."""
        src = _source()
        self.assertIn('_zz_temoin', src)
        self.assertIn('base, _ = os.path.splitext(nom)', src,
                      'le témoin ne dérive plus son nom du fichier mesuré')
        print("    OK 2 : le temoin vulture garde le prefixe du fichier")

    def test_l_outil_n_appelle_JAMAIS_ruff_fix(self):
        """⚠️ PIÈGE 3. `--fix` corrige des défauts antérieurs au lot. Un
        outil de MESURE qui corrige ne mesure plus ce qu'il rapporte.

        ⚠️ ET L'ANCRE EST L'ARBRE, PAS LE TEXTE : la docstring de l'outil
        NOMME `ruff --fix` pour expliquer pourquoi il ne l'appelle pas. Un
        `assertNotIn` sur le source entier échouait sur cette explication —
        le même défaut d'ancre qu'un commentaire pris pour du code.
        """
        arbre = ast.parse(_source())
        # ⚠️ ON EXCLUT PAR NŒUD, PAS PAR VALEUR : `ast.get_docstring` NORMALISE
        # le texte (dédente, rogne), donc comparer les chaînes ne reconnaît
        # aucune docstring. Deuxième défaut d'ancre du même test.
        docstrings = set()
        for n in ast.walk(arbre):
            corps = getattr(n, 'body', None)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)) and corps:
                premier = corps[0]
                if (isinstance(premier, ast.Expr)
                        and isinstance(premier.value, ast.Constant)
                        and isinstance(premier.value.value, str)):
                    docstrings.add(id(premier.value))
        litteraux = [n.value for n in ast.walk(arbre)
                     if isinstance(n, ast.Constant)
                     and isinstance(n.value, str)
                     and id(n) not in docstrings]
        fautifs = [x for x in litteraux if '--fix' in x]
        self.assertEqual(fautifs, [],
                         f'`--fix` apparaît dans du code : {fautifs}')
        print(f"    OK 3 : l'outil mesure, il ne corrige pas "
              f"({len(litteraux)} litteraux relus)")


class T2_LaRegleArbitree(unittest.TestCase):
    """⚠️ LE ZÉRO N'EST STRICT QUE SUR LES CODES DE CORRECTION. `RUF012` et
    `UP009` sont des préférences de style : la règle « +0 » sur eux avait fait
    sortir une fixture de sa classe pour la mettre là où elle est moins bien.
    Une règle de propreté qui arbitre la conception a cessé de servir.
    """

    def _constantes(self):
        arbre = ast.parse(_source())
        valeurs = {}
        for n in arbre.body:
            if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
                try:
                    valeurs[n.targets[0].id] = ast.literal_eval(n.value)
                except ValueError:
                    pass
        return valeurs

    def test_les_deux_familles_sont_DISTINCTES_et_declarees(self):
        v = self._constantes()
        stricts = set(v.get('CODES_STRICTS', ()))
        toleres = set(v.get('CODES_TOLERES', ()))
        self.assertTrue(stricts and toleres)
        self.assertEqual(stricts & toleres, set(),
                         'un code ne peut pas être strict ET toléré')
        for attendu in ('RUF012', 'UP009'):
            self.assertIn(attendu, toleres)
        for attendu in ('F', 'E', 'W', 'DTZ'):
            self.assertIn(attendu, stricts)
        print(f"    OK regle : {len(stricts)} familles strictes, "
              f"{len(toleres)} tolerees, aucune des deux")

    def test_le_motif_vulture_vise_les_classes_de_test(self):
        """⚠️ ET PAS UNE LISTE BLANCHE : elle deviendrait une liste à tenir."""
        motif = self._constantes().get('MOTIF_VULTURE', '')
        self.assertTrue(motif)
        for prefixe in ('T[0-9]*_*', 'V[0-9]_*'):
            self.assertIn(prefixe, motif)
        print("    OK motif : les classes de test sont exclues par MOTIF")


if __name__ == '__main__':
    unittest.main(verbosity=2)
