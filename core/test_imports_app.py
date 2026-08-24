"""Test — l'application n'importe pas un symbole que le dépôt a retiré.

⚠️ GATE : `py -m unittest discover -s core -t .` — voir test_frontiere_llm.py.

⚠️ ET C'EST POURQUOI CE FICHIER EST DANS `core/`. `actuaria_app.py` vit à la
racine et AUCUNE gate ne le découvre : c'est la règle Streamlit, et elle se
défend — l'interface ne se teste pas ici. Mais un IMPORT n'est pas de
l'affichage, et celui-là était cassé.

⚠️⚠️ MISE À JOUR — LOT 0.1 (25/08/2026). Ce fichier porte désormais un SECOND
contrôle, structurel : `LApplicationNeSExecutePasALImport`. Motif mesuré :
`actuaria_app.py` portait SIX instructions exécutantes au niveau module
(`set_page_config`, l'init du `session_state`, le style, `render_sidebar()`,
`page = st.session_state.page`, et le routeur). L'importer EXÉCUTAIT
l'application — donc ses 25 fonctions, 91 % du fichier, n'étaient atteignables
par AUCUN test. Le garde `if __name__ == "__main__"` ferme cela.

⚠️ CE QUE CE CONTRÔLE PROUVE, ET CE QU'IL NE PROUVE PAS. Il est STRUCTUREL : il
établit que rien ne s'exécute à l'import, PAS que l'interface fonctionne. La
vérification visuelle exigerait `streamlit`, absent de cet environnement — et
arbitré comme inutile, la bibliothèque étant destinée à être remplacée. La
réserve est donc assumée, et écrite ici plutôt que tue.

LE DÉFAUT, MESURÉ : l'application importait `export_pdf` depuis
`n5_rapport`, fonction RETIRÉE par le lot C1 (« Le PDF n'est plus GÉNÉRÉ :
il s'obtient par CONVERSION du Word ou du HTML »). Un lot avait supprimé une
fonction publique sans corriger son appelant. L'`ImportError` était attrapé
par un `except Exception` : l'app ne plantait pas, le bouton « Rapport PDF »
échouait à chaque clic en affichant à l'actuaire
`Erreur PDF : cannot import name 'export_pdf'`.

⚠️ LE RELEVÉ EXHAUSTIF A CONFIRMÉ L'ESTIMATION, pour une fois : sur tous les
`from <module interne> import <symbole>` du dépôt, celui-là était le SEUL
qui ne résolvait pas. Le défaut est isolé, pas systémique — ce test garde
donc le cas nommé plutôt que de rejouer le relevé complet, qui coûterait
l'import de tout le dépôt à chaque gate.
"""
import ast
import os
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(RACINE, 'actuaria_app.py')

#: Ce que le dépôt a retiré et que personne ne doit plus importer.
RETIRES = {
    ('direction_non_vie.provisionnement.a7_provisionnement.n5_rapport',
     'export_pdf'): 'retirée par le lot C1 — le PDF s\'obtient par '
                    'conversion du Word ou du HTML',
}


def _imports_de(chemin):
    """Les couples (module, symbole) importés par ce fichier."""
    with open(chemin, encoding='utf-8') as f:
        arbre = ast.parse(f.read())
    for n in ast.walk(arbre):
        if isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                yield (n.module, a.name), n.lineno


class LesSymbolesRetires(unittest.TestCase):

    def test_l_application_n_importe_aucun_symbole_retire(self):
        fautes = [(mod, sym, ligne)
                  for (mod, sym), ligne in _imports_de(APP)
                  if (mod, sym) in RETIRES]
        self.assertEqual(
            fautes, [],
            'l\'application importe un symbole retiré :\n' + '\n'.join(
                f'  actuaria_app.py:{ligne} — {mod}.{sym} ({RETIRES[(mod, sym)]})'
                for mod, sym, ligne in fautes))
        print('    OK : aucun symbole retiré n\'est importé par l\'app')

    def test_les_symboles_declares_retires_le_sont_VRAIMENT(self):
        """⚠️ SANS CE SECOND SENS, LA TABLE POURRAIT SE PÉRIMER : si la
        fonction revenait un jour, le test ci-dessus interdirait un import
        parfaitement valide."""
        import importlib
        for (mod, sym), raison in RETIRES.items():
            with self.subTest(symbole=f'{mod}.{sym}'):
                m = importlib.import_module(mod)
                self.assertFalse(
                    hasattr(m, sym),
                    f'{mod}.{sym} existe de nouveau : la table est à '
                    f'corriger ({raison})')
        print(f'    OK : les {len(RETIRES)} symbole(s) déclarés retirés le '
              f'sont réellement')


def _declenche(noeud):
    """Ce que l'expression DÉCLENCHE : un appel, ou un accès d'attribut.

    ⚠️ CALIBRÉ SUR LE FICHIER RÉEL, DANS LES DEUX SENS, avant d'être figé — un
    premier filtre, qui classait par TYPE de nœud AST, tenait
    `page = st.session_state.page` pour une DONNÉE parce que c'est un `Assign`.
    Ce n'est pas le type du nœud qui compte, c'est ce que l'instruction FAIT.
    Mesuré sur les 22 affectations de module : **21 données pures** (les 12
    couleurs, `VARIABLES_ATTENDUES`, `SYNONYMES_AUTO`, `AGENTS`, `STRUCTURE`,
    `RESULTATS`, `REGLE`, `SP`, `AGENTS_CALCULS`, `NIVEAU_LABELS`) et **1
    exécutante** — 0 faux positif, 0 faux négatif.
    """
    for n in ast.walk(noeud):
        if isinstance(n, ast.Call):
            return f'appel `{ast.unparse(n.func)[:40]}`'
        if isinstance(n, ast.Attribute):
            return f'attribut `{ast.unparse(n)[:40]}`'
    return None


def _est_garde_main(n):
    """`if __name__ == '__main__':` — la seule instruction de contrôle admise
    au niveau module."""
    t = getattr(n, 'test', None)
    return (isinstance(n, ast.If) and isinstance(t, ast.Compare)
            and isinstance(t.left, ast.Name) and t.left.id == '__name__'
            and len(t.comparators) == 1
            and isinstance(t.comparators[0], ast.Constant)
            and t.comparators[0].value == '__main__')


def _executantes(source):
    """Les instructions de niveau module qui S'EXÉCUTENT à l'import."""
    fautes = []
    for n in ast.parse(source).body:
        if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef,
                          ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant):
            continue                                   # docstring
        if _est_garde_main(n):
            continue                                   # le garde lui-même
        motif = _declenche(n)
        if motif:
            fautes.append((n.lineno, type(n).__name__, motif))
    return fautes


class LApplicationNeSExecutePasALImport(unittest.TestCase):
    """⚠️ CONTRÔLE POSITIF DU LOT 0.1 — il ÉCHOUAIT avant le correctif.

    Vérifié avant d'être figé : sur le fichier d'alors, il relevait bien les
    **six** instructions exécutantes, et il passait sur un fichier corrigé.
    Un contrôle qui passe déjà avant la correction n'épingle rien.
    """

    def test_aucune_instruction_ne_s_execute_a_l_import(self):
        with open(APP, encoding='utf-8') as f:
            fautes = _executantes(f.read())
        self.assertEqual(
            fautes, [],
            "actuaria_app.py s'exécute à l'import — aucune gate ne pourra le "
            "découvrir et ses fonctions redeviennent intestables :\n" +
            '\n'.join(f'  actuaria_app.py:{l} ({t}) — {m}'
                      for l, t, m in fautes))
        print("    OK : rien ne s'exécute à l'import de l'application")

    def test_le_point_d_entree_est_main_sous_garde(self):
        with open(APP, encoding='utf-8') as f:
            arbre = ast.parse(f.read())
        fns = {n.name for n in arbre.body if isinstance(n, ast.FunctionDef)}
        self.assertIn('main', fns, "l'application n'a pas de `main()`")
        gardes = [n for n in arbre.body if _est_garde_main(n)]
        self.assertEqual(
            len(gardes), 1,
            f"attendu UN `if __name__ == '__main__':`, trouvé {len(gardes)}")
        appels = {ast.unparse(c.func) for c in ast.walk(gardes[0])
                  if isinstance(c, ast.Call)}
        self.assertIn('main', appels,
                      "le garde n'appelle pas `main()`")
        print(f"    OK : point d'entrée unique `main()` sous garde "
              f"({len(fns)} fonctions désormais importables)")

    def test_le_controle_ATTRAPE_une_violation_plantee(self):
        """⚠️ LE SECOND SENS. Sans lui, ce contrôle pourrait devenir aveugle
        sans que rien ne le dise — c'est le motif que tout cet audit poursuit.
        Quatre formes plantées, quatre attrapées."""
        BASE = ('"""d"""\nimport streamlit as st\nNAVY = "#0F2E52"\n'
                'def main():\n    st.write(1)\n'
                'if __name__ == "__main__":\n    main()\n')
        self.assertEqual(_executantes(BASE), [], 'la base doit être propre')
        variantes = [
            ('un appel nu', BASE.replace('if __name__', 'main()\nif __name__')),
            ('une affectation qui lit `st`',
             BASE.replace('NAVY = "#0F2E52"', 'NAVY = st.secrets["c"]')),
            ("une boucle d'initialisation",
             BASE.replace('NAVY = "#0F2E52"',
                          'for k in ("a",):\n    st.session_state[k] = 1')),
            ('un try/except au niveau module',
             BASE.replace('NAVY = "#0F2E52"',
                          'try:\n    st.write(1)\nexcept Exception:\n    pass')),
        ]
        for libelle, source in variantes:
            with self.subTest(violation=libelle):
                self.assertNotEqual(
                    _executantes(source), [],
                    f'violation NON attrapée : {libelle} — le contrôle est '
                    f'aveugle à cette forme')
        print(f'    OK : {len(variantes)} violations plantées, '
              f'{len(variantes)} attrapées')


if __name__ == '__main__':
    unittest.main(verbosity=2)
