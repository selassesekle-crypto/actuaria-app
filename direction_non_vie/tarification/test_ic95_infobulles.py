"""Controle positif — constat `a3/C4` : les infobulles publient le VRAI IC 95 %.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
Deux infobulles d'A3 publiaient un intervalle de confiance FAUX :

    coefficients_glm     'IC 95% : [0.0000, 0.0000]'   deux zeros codes en dur
    relativites_poisson  'IC 95% : ['                  crochet ouvert, rien dedans

⚠️ ET LES VRAIES BORNES ETAIENT DEJA LA : `ci_low`/`ci_high` et
`ic95_low`/`ic95_high` sont lus quelques lignes plus haut, pour dessiner les
BARRES D'ERREUR du meme graphique. Le graphique tracait donc l'intervalle
juste, et l'ecrivait faux.

⚠️⚠️ POURQUOI LE ZERO ETAIT LA, ET CE QUE CA APPREND. Un `hovertemplate`
plotly est UNE chaine pour TOUTES les barres : une f-string ne peut y placer
qu'un SCALAIRE, jamais une valeur PAR POINT. L'auteur n'avait pas de mecanisme
-- il a mis `0`. *Le defaut ne venait pas d'une negligence mais d'une contrainte
non resolue ; `customdata` la resout.* Une valeur fabriquee faute de mecanisme
reste une valeur fabriquee : elle se declare, ou on trouve le mecanisme.

Aucun nombre n'est CALCULE ici : les bornes existent, elles sont AFFICHEES.
"""

from __future__ import annotations

import ast
import inspect
import re
import unicodedata
import unittest

from direction_non_vie.tarification.a3_glm import agent as mod_a3


def _source() -> str:
    return unicodedata.normalize('NFC', inspect.getsource(mod_a3))


class TestIC95Infobulles(unittest.TestCase):
    """Les bornes affichees sont celles qui sont tracees."""

    def test_aucun_zero_code_en_dur_ne_subsiste(self):
        """⚠️ La forme exacte du defaut d'origine, epinglee."""
        src = _source()
        self.assertEqual(
            src.count("'{:.4f}'.format(0)"), 0,
            "Un IC 95 % est de nouveau publié à partir d'un zéro codé en dur.")
        self.assertEqual(
            src.count('"IC 95% : [" +'), 0,
            "L'infobulle des relativités republie un crochet ouvert et vide.")

    def test_les_deux_infobulles_lisent_customdata(self):
        """Les deux sites doivent porter une valeur PAR POINT."""
        src = _source()
        trouves = re.findall(
            r'IC 95% : \[%\{customdata\[0\]:\.4f\}, %\{customdata\[1\]:\.4f\}\]',
            src)
        self.assertEqual(
            len(trouves), 2,
            f"{len(trouves)} infobulle(s) lisent les vraies bornes, 2 attendues "
            f"(coefficients β et relativités exp(β)).")

    def test_chaque_trace_qui_annonce_un_IC_fournit_son_customdata(self):
        """⚠️ Contrôle par AST — le second sens du précédent.

        Un `hovertemplate` qui cite `customdata` sans que la trace en reçoive
        afficherait un blanc : plotly ne lèverait pas, l'actuaire lirait
        « IC 95% : [, ] ». *Le silence ressemblerait au succès.*
        """
        arbre = ast.parse(_source())
        manquants = []
        for n in ast.walk(arbre):
            if not isinstance(n, ast.Call):
                continue
            cles = {k.arg for k in n.keywords if k.arg}
            if 'hovertemplate' not in cles:
                continue
            tpl = next((ast.unparse(k.value) for k in n.keywords
                        if k.arg == 'hovertemplate'), '')
            if 'customdata' in tpl and 'customdata' not in cles:
                manquants.append(f"ligne {n.lineno}")
        self.assertEqual(
            manquants, [],
            f"Trace(s) citant `customdata` sans le fournir : {manquants}. "
            f"L'infobulle afficherait un intervalle VIDE sans que rien ne "
            f"tombe.")

    def test_plotly_accepte_la_syntaxe_et_la_serialise(self):
        """⚠️ Second sens : la correction ne vaut que si plotly la comprend.

        Sans ce contrôle, une syntaxe invalide passerait tous les tests de
        source et échouerait seulement sous les yeux de l'actuaire.
        """
        import plotly.graph_objects as go

        fig = go.Figure(go.Bar(
            x=[1.0, 2.0], y=['a', 'b'], orientation='h',
            customdata=list(zip([0.5, 1.5], [1.5, 2.5])),
            hovertemplate=("IC 95% : [%{customdata[0]:.4f}, "
                           "%{customdata[1]:.4f}]<extra></extra>")))
        trace = fig.data[0]
        self.assertIn('customdata[0]', trace.hovertemplate)
        premier = next(iter(trace.customdata))
        self.assertEqual(list(premier), [0.5, 1.5])
        self.assertTrue(fig.to_json(), "La figure ne se sérialise plus.")

    def test_les_bornes_affichees_sont_celles_des_barres_d_erreur(self):
        """⚠️ La propriété qui compte : une SEULE source pour les deux usages.

        Contrôle par AST : la trace des coefficients doit tirer son
        `customdata` de `ci_low`/`ci_high` — les variables mêmes qui servent à
        `errors`. Deux sources donneraient un graphique qui trace un
        intervalle et en écrit un autre : exactement le défaut d'origine.
        """
        src = _source()
        self.assertIn('customdata    = list(zip(ci_low, ci_high))', src)
        self.assertIn('customdata    = list(zip(ic_low, ic_high))', src)
        self.assertIn('errors  = [abs(h - v) for v, h in zip(vals, ci_high)]',
                      src)


if __name__ == '__main__':
    unittest.main()
