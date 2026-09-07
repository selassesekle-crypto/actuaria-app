"""LE LIFT PUBLIE EST MESURE, PAS DESSINE -- constat `A4-2`.

A4 produisait une figure `lift_chart` dont les valeurs etaient une fonction
AFFINE du rang du decile, tiree du seul scalaire Gini :

    lifts = [max(0.1, 1 + (gini * 3) * (d - 5.5) / 5.5) for d in deciles]

Mesure : differences secondes exactement nulles a `gini` = 0,10 et 0,25 --
une DROITE. Le commentaire l'appelait << approximation analytique basee sur
la courbe de Lorenz >> ; une courbe de Lorenz ne donne pas une droite, et
rien ici ne regardait le portefeuille.

⚠️⚠️ ET LE VRAI CONSTAT ETAIT SON MOTIF D'EXCLUSION.
`FIGURES_ECARTEES['lift_chart']` disait << doublon -- chart_lift_decile, meme
mesure >>. Faux : la figure PUBLIEE recoit `lift_deciles_wf`, calcule dans
`a6._backtesting_temporel` -- la moyenne OBSERVEE par decile de risque predit,
issue du walk-forward. *Le seul rempart entre une courbe fabriquee et le
rapport signe etait une raison d'exclusion inexacte -- qui la lit peut
conclure qu'on peut la retablir.*

⚠️ LA REFERENCE EST UN NOM DE FONCTION, PAS UN NUMERO DE LIGNE. J'avais ecrit
`a6:2177`, repris du rapport d'audit : le numero etait DEJA FAUX quand je
l'ecrivais -- 2177 porte une boucle sur les tranches d'age, le calcul vit a
2229. LM-3 resout donc par le NOM, et non par la position.

  LM-1  A4 ne produit plus AUCUN lift fabrique ;
  LM-2  et l'entree du catalogue ne survit pas a sa figure ;
  LM-3  le lift PUBLIE, lui, vient d'une moyenne OBSERVEE.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import unittest

from direction_non_vie.tarification.services import rapport_modeles_tarif as R


class TestLiftMesure(unittest.TestCase):

    def test_LM1_A4_ne_produit_plus_de_lift_fabrique(self):
        """⚠️ PAR AST, pas par recherche de texte : on cherche l'AFFECTATION
        `graphiques['lift_chart'] = ...`, pas le mot dans un commentaire --
        sans quoi la note qui explique le retrait ferait echouer le controle
        qu'elle documente."""
        chemin = (pathlib.Path(__file__).resolve().parent / 'a4_ml'
                  / 'agent.py')
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        fautifs = []
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Assign):
                continue
            for cible in noeud.targets:
                if (isinstance(cible, ast.Subscript)
                        and isinstance(cible.slice, ast.Constant)
                        and cible.slice.value == 'lift_chart'):
                    fautifs.append(noeud.lineno)
        self.assertEqual(
            fautifs, [],
            f'A4 produit encore une figure `lift_chart` (lignes {fautifs}) : '
            f'une courbe dessinee depuis un scalaire, pas mesuree')
        print('    LM-1 A4 ne produit plus de lift fabrique')

    def test_LM2_l_entree_du_catalogue_ne_survit_pas_a_sa_figure(self):
        """⚠️ Une justification d'exclusion sans objet finit par etre relue
        comme une autorisation de retablir."""
        self.assertNotIn(
            'lift_chart', R.FIGURES_ECARTEES,
            "`lift_chart` est encore ECARTEE alors que le code qui la "
            "produisait est supprime : l'entree a survecu a sa figure")
        self.assertNotIn('lift_chart', R.SOURCES_FIGURES)
        print('    LM-2 catalogue : plus aucune entree pour `lift_chart`')

    def test_LM3_le_lift_publie_vient_d_une_moyenne_OBSERVEE(self):
        """⚠️⚠️ LE CONTROLE QUI COMPTE. Retirer la figure fabriquee ne dit rien
        de celle qui reste : on verifie que `chart_lift_decile` est bien
        alimentee par une mesure, et non par un second dessin.

        `lift_deciles_wf` est construit par une moyenne des valeurs OBSERVEES
        dans chaque decile de risque PREDIT -- deux ingredients qu'une droite
        tiree d'un scalaire ne peut pas avoir.
        """
        self.assertIn('chart_lift_decile', R.SOURCES_FIGURES,
                      'la figure de lift publiee a disparu du catalogue')
        from direction_non_vie.tarification.a6_comparaison import agent as A6
        # ⚠️ ON RESOUT LA FONCTION NOMMEE DANS LA PROSE : si elle est renommee
        # ou disparait, ce test rougit et la prose qui la cite se relit. C'est
        # le pendant executable de la reference `a6._backtesting_temporel`.
        self.assertTrue(
            hasattr(A6.AgentA6Comparaison, '_backtesting_temporel'),
            'la fonction citee par la prose du retrait n existe plus : '
            '`a6._backtesting_temporel`')
        source = inspect.getsource(
            A6.AgentA6Comparaison._backtesting_temporel)
        # ⚠️ TOUTES LES AFFECTATIONS, PAS LA PREMIERE. Ma premiere version
        # prenait `next(...)` et tombait sur la DECLARATION
        # (`lift_deciles_wf = None`) : elle mesurait l'initialisation, pas le
        # calcul. *Un releve qui s'arrete au premier resultat mesure ce qui
        # vient en tete du fichier, pas ce qui compte.*
        lignes = [x.strip() for x in source.split('\n')
                  if 'lift_deciles_wf' in x and '=' in x
                  and not x.strip().startswith('#')]
        self.assertTrue(lignes, '`lift_deciles_wf` n est plus calcule')
        calculs = [x for x in lignes if '= None' not in x]
        self.assertTrue(
            calculs, f'`lift_deciles_wf` n est plus QUE declare : {lignes}')
        self.assertTrue(
            any('mean' in x for x in calculs),
            f'le lift publie ne vient plus d une MOYENNE : {calculs}')
        for x in calculs:
            self.assertNotIn('gini', x.lower(),
                             f'le lift publie est derive du Gini : {x}')
        print(f'    LM-3 lift publie : {calculs[0][:66]}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
