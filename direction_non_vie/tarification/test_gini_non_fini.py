# -*- coding: utf-8 -*-
"""
=============================================================================
  UN GINI `nan` NE TRAVERSE PLUS AUCUN GARDE-FOU
=============================================================================

⚠️⚠️ CE N'ETAIT PAS UN ZERO FABRIQUE, C'ETAIT UN `nan` -- ET C'EST PIRE.

Mesure du 03/09/2026. `A5._calculer_gini` n'avait AUCUNE garde sur la somme
nulle, contrairement a ses deux voisins. Sur un jeu de test sans sinistre :

    np.cumsum(y) / np.sum(y)  ->  nan partout, RuntimeWarning

**Un RuntimeWarning n'est pas une exception** : l'`except` en fin de fonction
ne tirait donc jamais, et `np.clip(nan, -1, 1)` reste `nan`. A5 publiait un
Gini `nan`.

-----------------------------------------------------------------------------
POURQUOI C'EST UN DEFAUT DE RANG 1
-----------------------------------------------------------------------------
Un `nan` franchit les gardes ecrites pour un NOMBRE et celles ecrites pour
une ABSENCE :

    nan < 0        -> False   l'anti-selection ne tire pas
    nan is None    -> False   la reserve ne se declenche pas
                              A6 ne l'ecarte PAS du catalogue
    sorted([...])  -> le nan reste a sa POSITION initiale, toute comparaison
                      avec lui etant fausse
    f"{nan:.4f}"   -> "nan", sans plantage : il SORT tel quel

Consequence mesuree : **un modele NON EVALUE pouvait se classer devant un
meilleur**, en silence. Et A5 produit les modeles Deep Learning, candidats a
la production -- donc au TARIF.

  *Un `nan` n'est ni un nombre utilisable ni une absence : il franchit les
  gardes ecrites pour l'un ET pour l'autre.*

-----------------------------------------------------------------------------
TROIS GESTES, AU POINT D'ETRANGLEMENT
-----------------------------------------------------------------------------
  1. A5 cesse de PRODUIRE un `nan` (garde somme nulle, comme A3 et A4) ;
  2. A6 ecarte tout Gini NON FINI, pas seulement `None` -- la garde est au
     point d'etranglement, elle couvre toute source future ;
  3. `etats_gini` classe le non-fini en `NON_MESURE` -- c'est la que la
     reserve et l'anti-selection decident.

⚠️ Un seul des trois aurait laisse un chemin ouvert : corriger A5 seul
n'aurait rien fait contre un `nan` venu d'ailleurs, et corriger A6 seul
aurait laisse A5 publier une valeur fausse dans son propre rapport.
=============================================================================
"""

import unittest

import numpy as np

from core.conformite_reglementaire import (
    GINI_NON_MESURE,
    etats_gini,
    modeles_anti_selectifs,
    statut_anti_selection,
    synthese_gini_non_mesure,
)
from direction_non_vie.tarification.a6_comparaison.agent import (
    AgentA6Comparaison,
)

_NAN = float('nan')
_INF = float('inf')


def _metriques(gini_tweedie):
    return {'poisson': {'gini': 0.22}, 'gamma': {'gini': 0.11},
            'tweedie': {'gini': gini_tweedie}}


def _resultats(gini_dl):
    """Trois agents sur la MEME cible, seul le DL portant la valeur testee."""
    return (
        {'success': True, 'metriques': {
            'tweedie': {'gini': 0.25, 'cible': 'prime_pure'}}},
        {'success': True, 'col_cible': 'prime_pure', 'metriques': {
            'xgboost': {'gini_test': 0.28, 'cible': 'prime_pure'}}},
        {'success': True, 'col_cible': 'prime_pure', 'metriques': {
            'cann': {'gini_test': gini_dl, 'cible': 'prime_pure'}}},
    )


class T1_A5NeProduitPlusDeNan(unittest.TestCase):

    def test_nf_1_A5_rend_un_nombre_FINI_sur_un_test_sans_sinistre(self):
        """NF-1 : la garde qui manquait, eprouvee sur la VRAIE methode.

        ⚠️ Contrat RENFORCE le 03/09/2026 (lot « 0.0 fabriques »). Ce test
        exigeait « un nombre fini, quelle que soit la valeur qui remplace le
        nan » — et la valeur de remplacement etait un 0.0 qui affirmait un
        pouvoir discriminant nul que rien n'avait mesure. Sur un test sans
        sinistre, la mesure N'EXISTE PAS : la methode rend `None`, ni nan
        (division par zero non gardee) ni 0.0 (mesure fabriquee). Voir
        test_gini_none_pas_zero.py pour la chaine complete.
        """
        from direction_non_vie.tarification.a5_deep_learning.agent import (
            AgentA5DeepLearning,
        )
        a5 = AgentA5DeepLearning.__new__(AgentA5DeepLearning)
        pred = np.random.RandomState(0).rand(100)
        gini = a5._calculer_gini(np.zeros(100), pred)
        self.assertIsNone(
            gini,
            f"A5 publie {gini!r} sur un test sans sinistre : la mesure "
            f"n'existe pas, elle se dit None — ni un nan (division par zero "
            f"non gardee, un RuntimeWarning n'est pas une exception) ni un "
            f"0.0 (pouvoir discriminant nul que rien n'a mesure)")

    def test_nf_2_les_trois_agents_ont_LA_MEME_garde(self):
        """NF-2 : l'asymetrie entre voisins etait le revelateur.

        A3 et A4 gardaient la somme nulle, A5 non. *L'asymetrie entre
        voisins est le revelateur le moins cher de tout l'audit.*
        """
        import ast
        import inspect
        import textwrap
        for module, classe in (
                ('a3_glm', 'AgentA3GLM'),
                ('a4_ml', 'AgentA4ML'),
                ('a5_deep_learning', 'AgentA5DeepLearning')):
            mod = __import__(
                f'direction_non_vie.tarification.{module}.agent',
                fromlist=['agent'])
            fonction = getattr(mod, classe)._calculer_gini
            # ⚠️ `textwrap.dedent`, PAS `inspect.cleandoc` : cette derniere
            # normalise une DOCSTRING, pas du CODE -- elle casse
            # l'indentation et `ast.parse` leve. Deuxieme fois aujourd'hui.
            arbre = ast.parse(
                textwrap.dedent(inspect.getsource(fonction))).body[0]
            # ⚠️ L'ASSIETTE EST LE CORPS, JAMAIS LA DOCSTRING : celle d'A5
            # cite desormais la division fautive pour l'expliquer. *Une
            # citation n'est pas une affirmation, et surtout pas un garde.*
            instructions = [n for n in arbre.body
                            if not (isinstance(n, ast.Expr)
                                    and isinstance(n.value, ast.Constant))]
            corps = '\n'.join(ast.unparse(n) for n in instructions)
            with self.subTest(agent=module):
                self.assertIn(
                    'np.sum(y_true) == 0', corps,
                    f"{module} n'a pas de garde sur la somme nulle DANS SON "
                    f"CODE : il divisera par zero et publiera un `nan`")


class T2_LeNanNeTraversePlusRien(unittest.TestCase):
    """⚠️⚠️ LE CONTROLE DEMANDE NOMMEMENT : plus AUCUN garde-fou traverse."""

    def test_nf_3_etats_gini_classe_tout_NON_FINI_en_NON_MESURE(self):
        """NF-3 : `nan` EST un `float` -- il passait par la branche des
        nombres, `isinstance(nan, float)` etant vrai."""
        for valeur in (_NAN, _INF, -_INF):
            with self.subTest(valeur=repr(valeur)):
                self.assertEqual(
                    etats_gini(_metriques(valeur))['tweedie'],
                    GINI_NON_MESURE)
        # ⚠️ second sens : un nombre FINI reste un nombre
        self.assertEqual(etats_gini(_metriques(0.15))['tweedie'], 0.15)
        self.assertEqual(etats_gini(_metriques(-0.078))['tweedie'], -0.078)

    def test_nf_4_UN_NAN_NE_TRAVERSE_AUCUN_GARDE_FOU(self):
        """NF-4 : LE CONTROLE CENTRAL -- les quatre gardes, d'un coup.

        ⚠️ Avant les trois gestes, ce test aurait echoue sur les QUATRE
        lignes : l'anti-selection ne tirait pas, la reserve non plus, A6
        n'ecartait pas, et le classement gardait le modele.
        """
        met = _metriques(_NAN)

        # 1. il n'est PAS pris pour une anti-selection (ce serait un verdict)
        self.assertEqual(
            modeles_anti_selectifs(met), [],
            "un Gini non mesurable est compte comme anti-selectif : "
            "c'est un VERDICT sur une ABSENCE")
        self.assertEqual(statut_anti_selection('VERT', met), 'VERT')

        # 2. mais il DECLENCHE la reserve (l'absence se declare)
        reserve = synthese_gini_non_mesure(met)
        self.assertIsNotNone(
            reserve, "un Gini `nan` ne declenche pas la reserve : "
                     "l'absence n'est ni jugee ni declaree, elle est TUE")
        self.assertIn('tweedie', reserve)

        # 3. et A6 l'ECARTE du catalogue
        a6 = AgentA6Comparaison.__new__(AgentA6Comparaison)
        exc_m = a6._agreger_resultats(
            *_resultats(_NAN), col_cible='prime_pure')[2]
        self.assertIn(
            'DL_CANN', [x['modele'] for x in exc_m],
            "A6 garde au catalogue un modele au Gini `nan` : il reste "
            "candidat a la PRODUCTION")

        # 4. donc il ne peut plus etre classe
        catalogue = a6._agreger_resultats(
            *_resultats(_NAN), col_cible='prime_pure')[0]
        self.assertNotIn('DL_CANN', [m['modele'] for m in catalogue])

    def test_nf_5_A6_ecarte_NON_FINI_et_None_mais_GARDE_un_gini_normal(self):
        """NF-5 : le second sens. Un filtre qui ecarte tout ne filtre rien."""
        a6 = AgentA6Comparaison.__new__(AgentA6Comparaison)
        for valeur, doit_etre_ecarte in ((_NAN, True), (None, True),
                                         (_INF, True), (-_INF, True),
                                         (0.10, False), (-0.05, False),
                                         (0.0, False)):
            catalogue, _, exc_m = a6._agreger_resultats(
                *_resultats(valeur), col_cible='prime_pure')
            ecarte = 'DL_CANN' in [x['modele'] for x in exc_m]
            with self.subTest(gini=repr(valeur)):
                self.assertEqual(
                    ecarte, doit_etre_ecarte,
                    f"Gini={valeur!r} : ecarte={ecarte}, "
                    f"attendu={doit_etre_ecarte}")
                if not doit_etre_ecarte:
                    self.assertIn('DL_CANN',
                                  [m['modele'] for m in catalogue])

    def test_nf_6_la_raison_de_l_exclusion_NOMME_la_valeur_fautive(self):
        """NF-6 : << non mesure >> ne suffit pas -- laquelle, et pourquoi ?

        ⚠️ La raison disait << publie a None par l'agent source >> alors que
        la valeur pouvait etre `nan` : le message affirmait une valeur qu'il
        n'avait pas lue.
        """
        a6 = AgentA6Comparaison.__new__(AgentA6Comparaison)
        exc_m = a6._agreger_resultats(
            *_resultats(_NAN), col_cible='prime_pure')[2]
        raison = exc_m[0]['raison']
        self.assertIn('nan', raison.lower(),
                      f"la raison ne nomme pas la valeur fautive : {raison}")
        self.assertIn('fabriquée', raison)


if __name__ == '__main__':
    unittest.main(verbosity=2)
