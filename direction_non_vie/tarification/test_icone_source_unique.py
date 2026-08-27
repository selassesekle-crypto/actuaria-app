"""Controle positif — le `icone` local ne duplique plus `glyphe_rag`.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
Les quatre agents de tarification recopiaient a l'identique :

    icone = "✅" if statut=="VERT" else "⚠️" if statut=="AMBRE" else "❌"

C'etait CORRECT partout ce jour-la -- et rien n'empechait la cinquieme copie
de diverger. C'est exactement ce qui s'etait produit sur les glyphes BINAIRES
d'A6, ou un statut ROUGE affichait le glyphe de l'AMBRE.

⚠️ L'ASSIETTE EST LE PERIMETRE TARIFICATION, ET C'EST MESURE. Le dépôt compte
**11 sites** portant un `icone` a glyphes, dans QUATRE directions, et **4
formes distinctes** -- dont `"✅" if ok else "⏸"`, qui n'est PAS du RAG. Les
sept autres appartiennent a `reglementation` et `direction_vie_epre` : les
toucher ouvrirait d'autres chantiers. *Un lot mecanique ne l'est que sur son
perimetre.*

⚠️ ET LA VERIFICATION EST PAR EXECUTION. La scorecard qui porte ce site vit
dans `graphiques_validation`, pas dans `graphiques` : une premiere sonde a
cherche au mauvais endroit et n'a rien trouve. *Le chemin s'execute, encore
faut-il regarder ou il aboutit.*
"""

from __future__ import annotations

import ast
import inspect
import re
import unicodedata
import unittest

from core.charts_tarif import GLYPHE_RAG

_AGENTS = ('a3_glm', 'a4_ml', 'a5_deep_learning', 'a6_comparaison')


def _source(agent: str) -> str:
    mod = __import__(
        f'direction_non_vie.tarification.{agent}.agent', fromlist=['agent'])
    return unicodedata.normalize('NFC', inspect.getsource(mod))


class TestIconeSourceUnique(unittest.TestCase):
    """Un seul endroit decide du glyphe, et le rendu le prouve."""

    def test_aucun_agent_ne_recopie_la_table_des_glyphes(self):
        """⚠️ La forme exacte de la duplication, epinglee dans les quatre."""
        fautifs = []
        for agent in _AGENTS:
            src = _source(agent)
            for i, ligne in enumerate(src.split('\n'), 1):
                if re.search(r'=\s*[\'"]✅[\'"]\s+if\s+\w+\s*==', ligne):
                    fautifs.append(f"{agent}:{i}")
        self.assertEqual(
            fautifs, [],
            f"Table de glyphes recopiée localement : {fautifs}. Une copie "
            f"correcte aujourd'hui peut diverger demain — c'est ce qui est "
            f"arrivé aux glyphes binaires d'A6.")

    def test_les_quatre_agents_lisent_la_source(self):
        """⚠️ Contrôle par AST : l'appel doit exister, et l'import le précéder.

        Un import manquant ne se voit PAS à l'import du module — seulement à
        l'exécution de la fonction. C'est la leçon des 23 orphelines.
        """
        for agent in _AGENTS:
            arbre = ast.parse(_source(agent))
            imports = [n.lineno for n in ast.walk(arbre)
                       if isinstance(n, ast.ImportFrom)
                       and any(a.name == 'glyphe_rag' for a in n.names)]
            appels = [n.lineno for n in ast.walk(arbre)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                      and n.func.id == 'glyphe_rag']
            self.assertTrue(imports, f"{agent} n'importe pas `glyphe_rag`.")
            self.assertTrue(appels, f"{agent} n'appelle pas `glyphe_rag`.")
            self.assertTrue(
                all(a > min(imports) for a in appels),
                f"{agent} : `glyphe_rag` appelé avant son import.")

    def test_le_rendu_reel_porte_les_TROIS_glyphes(self):
        """⚠️⚠️ CONCLU PAR EXÉCUTION — et au bon endroit.

        La scorecard vit dans `graphiques_validation`, pas dans `graphiques`.
        Une sonde qui cherche au mauvais endroit ne trouve rien et conclut à
        tort. On construit la figure et on lit ses étiquettes.
        """
        import sys
        from pathlib import Path

        chemin = Path(__file__).resolve().parent / 'a6_comparaison'
        if str(chemin) not in sys.path:
            sys.path.insert(0, str(chemin))
        import test_a6_comparaison as fixtures

        from direction_non_vie.tarification.a6_comparaison.agent import (
            AgentA6Comparaison,
        )

        agent = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp',
                                   verbose=False)
        resultat = agent.run(
            result_a2=fixtures._make_r_a2_avec_annee(600),
            result_a3=fixtures._make_r_a3(), result_a4=fixtures._make_r_a4(),
            generer_graphiques=True, col_cible='nb_sinistres')

        figure = (resultat.get('graphiques_validation') or {}).get(
            'scorecard_selection')
        self.assertIsNotNone(
            figure,
            "`scorecard_selection` n'est plus produite : ce test ne prouve "
            "plus rien sur le rendu.")

        etiquettes = []
        for trace in figure.data:
            texte = getattr(trace, 'text', None)
            if isinstance(texte, str):
                etiquettes.append(texte)
            elif texte is not None:
                etiquettes += [str(v) for v in texte]
        self.assertTrue(etiquettes, "Aucune étiquette dans la scorecard.")
        for etiquette in etiquettes:
            self.assertTrue(
                any(g in etiquette for g in GLYPHE_RAG.values()),
                f"L'étiquette « {etiquette} » ne porte aucun glyphe de la "
                f"source unique.")

    def test_les_sites_HORS_tarification_ne_sont_PAS_touches(self):
        """⚠️⚠️ SECOND SENS — l'assiette du lot, figée.

        Sept sites vivent dans `reglementation` et `direction_vie_epre`, avec
        des formes DIFFÉRENTES — dont une qui n'est pas du RAG. Les toucher
        ouvrirait d'autres chantiers. Ce test tombe si quelqu'un déborde.
        """
        import pathlib

        racine = pathlib.Path(__file__).resolve().parents[2]
        hors = 0
        for chemin in sorted(racine.rglob('*.py')):
            texte = chemin.as_posix()
            if 'tarification' in texte or '.venv' in texte:
                continue
            if chemin.name.startswith('test_'):
                continue
            try:
                contenu = unicodedata.normalize(
                    'NFC', chemin.read_text(encoding='utf-8', errors='replace'))
            except OSError:
                continue
            hors += len(re.findall(r'\bicones?\w*\s*=\s*[\[\'"].{0,4}✅', contenu))
        self.assertGreaterEqual(
            hors, 5,
            f"{hors} site(s) `icone` hors tarification (7 mesurés le 27/08). "
            f"S'ils ont bougé, c'est qu'un autre chantier a été ouvert — ou "
            f"que l'assiette doit être re-mesurée.")


if __name__ == '__main__':
    unittest.main()
