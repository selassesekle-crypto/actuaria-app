# -*- coding: utf-8 -*-
"""La gate voit-elle tout ce qu'elle prétend certifier ?

⚠️ POURQUOI CE TEST EXISTE. `unittest discover` sur `a13_audit` rendait
« Ran 0 tests — NO TESTS RAN » et sortait en 0. Sept tests réels ne tournaient
pas, et la gate déclarait le succès. Le défaut n'était pas dans les tests : il
était dans l'instrument, qui ne distingue pas « rien à faire ici » de « je ne
sais pas lire ce fichier ». Le silence ressemblait au succès.

⚠️ CE QUE LE RELEVÉ A RENDU, ET QUI A BATTU L'ESTIMATION. J'avais trouvé trois
fichiers en Non-Vie. Le relevé exhaustif en a rendu CINQ, sur DEUX zones, et
les deux derniers sont pires : nommés `tests.py`, ils échappent à unittest ET
à pytest — aucun changement de gate ne les aurait rattrapés, seul un
changement de nom le peut.

⚠️ CE TEST NE CONVERTIT RIEN, IL MESURE. Réparer cinq fichiers répare
aujourd'hui ; ce garde-fou est ce qui empêche le sixième d'arriver en silence.
Même motif que `test_frontiere_llm` pour la frontière API et que
`test_proprete_outil` pour l'outil de propreté.
"""
import ast
import fnmatch
import os
import unittest

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Chaque zone de la gate, et l'outil qui la lit. ⚠️ La gate est en QUATRE
#: commandes : trois `unittest discover`, une `pytest`. Les deux outils ne
#: collectent pas les mêmes fichiers, et c'est toute la question.
ZONES = (
    ('direction_non_vie', 'unittest'),
    ('normes', 'unittest'),
    ('core', 'unittest'),
    ('direction_vie_epre', 'pytest'),
    ('direction_sante_prevoyance', 'pytest'),
)

#: `unittest discover` cherche `test*.py` -- et ne collecte QUE les méthodes
#: des sous-classes de `TestCase`. Une fonction `test_x()` au niveau module
#: lui est invisible, même dans un fichier au bon nom.
MOTIF_UNITTEST = 'test*.py'

#: pytest collecte `test_*.py` et `*_test.py`, et y prend AUSSI les fonctions
#: de niveau module. Son angle mort est donc le NOM, pas la structure.
MOTIFS_PYTEST = ('test_*.py', '*_test.py')


def _porte_des_tests(arbre):
    """(nb de fonctions `test_*` au niveau module, nb de classes TestCase)."""
    fonctions = sum(
        1 for n in arbre.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name.startswith('test_'))
    classes = sum(
        1 for n in ast.walk(arbre)
        if isinstance(n, ast.ClassDef)
        and any('TestCase' in ast.unparse(b) for b in n.bases))
    return fonctions, classes


def _invisible(nom_fichier, outil, fonctions, classes):
    """Ce fichier porte des tests : la gate de sa zone les verrait-elle ?"""
    if outil == 'unittest':
        if not fnmatch.fnmatch(nom_fichier, MOTIF_UNITTEST):
            return f'nom hors du motif « {MOTIF_UNITTEST} »'
        if classes == 0 and fonctions > 0:
            return (f'{fonctions} fonction(s) `test_*` au niveau module, '
                    f'aucune classe `TestCase` : unittest ne les collecte pas')
        return None
    if not any(fnmatch.fnmatch(nom_fichier, m) for m in MOTIFS_PYTEST):
        motifs = ', '.join(MOTIFS_PYTEST)
        return (f'nom hors des motifs pytest {motifs} -- invisible aux '
                f'DEUX outils')
    return None


def relever_invisibles():
    """Les fichiers qui portent des tests que leur gate ne lira jamais."""
    manques = []
    for zone, outil in ZONES:
        racine_zone = os.path.join(_RACINE, zone)
        for dossier, _, fichiers in os.walk(racine_zone):
            for nom in fichiers:
                if not nom.endswith('.py'):
                    continue
                chemin = os.path.join(dossier, nom)
                try:
                    with open(chemin, encoding='utf-8') as f:
                        arbre = ast.parse(f.read())
                except (OSError, SyntaxError, UnicodeDecodeError):
                    continue
                fonctions, classes = _porte_des_tests(arbre)
                if not fonctions and not classes:
                    continue
                cause = _invisible(nom, outil, fonctions, classes)
                if cause:
                    relatif = os.path.relpath(chemin, _RACINE)
                    manques.append((relatif.replace(os.sep, '/'), cause))
    return sorted(manques)


class T5G_CouvertureDeLaGate(unittest.TestCase):
    """Aucun test ne doit exister hors de portée de la gate qui le couvre."""

    def test_aucun_fichier_de_test_n_echappe_a_sa_gate(self):
        manques = relever_invisibles()
        if manques:
            detail = '\n'.join(f'    {c}\n        -> {r}'
                               for c, r in manques)
            self.fail(
                f'{len(manques)} fichier(s) portent des tests que la gate ne '
                f'lit PAS. La gate sortirait en 0 sans les avoir executes -- '
                f'le silence ressemblerait au succes :\n{detail}')

    def test_le_releve_couvre_les_cinq_zones_de_la_gate(self):
        """⚠️ Un garde-fou qui ne regarde qu'une zone est pire que rien : il
        rassure sur ce qu'il n'a pas vu."""
        self.assertEqual(len(ZONES), 5)
        for zone, outil in ZONES:
            self.assertTrue(os.path.isdir(os.path.join(_RACINE, zone)), zone)
            self.assertIn(outil, ('unittest', 'pytest'))


if __name__ == '__main__':
    unittest.main()
