"""Test — l'application n'importe pas un symbole que le dépôt a retiré.

⚠️ GATE : `py -m unittest discover -s core -t .` — voir test_frontiere_llm.py.

⚠️ ET C'EST POURQUOI CE FICHIER EST DANS `core/`. `actuaria_app.py` vit à la
racine et AUCUNE gate ne le découvre : c'est la règle Streamlit, et elle se
défend — l'interface ne se teste pas ici. Mais un IMPORT n'est pas de
l'affichage, et celui-là était cassé.

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


if __name__ == '__main__':
    unittest.main(verbosity=2)
