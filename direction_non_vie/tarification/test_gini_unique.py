# -*- coding: utf-8 -*-
"""TROIS CODES CALCULAIENT LE MEME GINI, ET ILS N'ETAIENT PAS D'ACCORD (lot 3).

Le controle `pipeline/C3` mesurait depuis le 01/09/2026 combien de fonctions du
depot calculent un Gini. Il en comptait six. **Personne n'avait verifie
qu'elles rendaient la meme valeur.** Mesure du 05/09/2026 :

    `a3` trie par `argsort(-y_pred)`        -- sans `mergesort`
    `a4` et `a5` par `argsort(y_pred)[::-1]` -- tri croissant PUIS renverse,
                                               ce qui INVERSE les ex aequo

Sur 500 lignes et 8 paliers de prediction, les trois rendent **0,027476**,
**0,046857** et **0,035429** pour la meme donnee. Et sur des predictions
TOUTES EGALES -- un modele qui ne separe rien, dont le vrai Gini est ZERO --
deux d'entre eux rendent des valeurs de **SIGNES OPPOSES**, tirees de l'ordre
des lignes du fichier.

⚠️⚠️ ET J'AVAIS SURESTIME LA PORTEE, LA MESURE M'A CORRIGE. J'ai annonce que
l'ordre des lignes pouvait changer le modele publie par A6. **Faux** : ces
0,01 venaient de predictions SYNTHETIQUES a 3 et 8 paliers. Sur les
predictions REELLES d'un GLM (2 373 valeurs distinctes sur 2 500, 5,8 % en ex
aequo), l'ecart entre conventions vaut au plus **0,000053** -- deux ordres de
grandeur sous les marges de classement d'A6. *Un chiffre juste sur la mauvaise
assiette repond a une autre question.*

Ce qui reste, et qui justifie le lot : **`a3:cout_moyen` predit UNE SEULE
valeur pour 2 500 contrats** ; le vrai Gini y est zero, et les trois
conventions rendaient -0,000349, -0,000349 et **+0,000349**. Plus la
duplication elle-meme.

LA SORTIE : une seule formule, dans `core.validation_tarif.gini_lorenz`, qui
TRAITE LES EX AEQUO -- la cible est remplacee par la moyenne du palier, ce qui
rend le calcul **invariant par permutation** des lignes. `a3`, `a4` et `a5`
delegent ; chacun garde SON contrat d'absence et SON bornage a sa frontiere.

⚠️ MESURE DE L'UNIFICATION, sur `auto` 2 500 : modeles de production
INCHANGES (`GLM_POISSON`, `GLM_TWEEDIE`), classement inchange, statuts
inchanges, **prime totale identique au centime**. Cinq chiffres de diagnostic
bougent, dont le Gini du Gamma : -0,0298 -> **-0,0283**, VERS zero.

⛔ DEUX IMPLEMENTATIONS RESTENT, ET C'EST DELIBERE -- voir `GU-6`.

Ce que cette sentinelle exige :
  GU-1  ⚠️⚠️ le Gini du socle est INVARIANT PAR PERMUTATION des lignes, et
        les trois anciens tris ne l'etaient PAS (le second sens, mesure) ;
  GU-2  une prediction CONSTANTE rend ZERO, la ou un tri simple rend ±0,026 ;
  GU-3  sans ex aequo, il COINCIDE exactement avec un tri simple ;
  GU-4  `a3`, `a4` et `a5` rendent EXACTEMENT la meme valeur -- verifie par
        EXECUTION, pas par lecture ;
  GU-5  ils ne CALCULENT plus : releve AST, leur corps n'emploie plus
        `cumsum` ;
  GU-6  ⚠️ les deux implementations NON deleguees sont NOMMEES et leur raison
        est ECRITE dans le code ;
  GU-7  chaque frontiere garde son contrat d'absence et son bornage.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""
import ast
import os
import pathlib
import sys
import unittest

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

import numpy as np

from core.validation_tarif import gini_lorenz

#: Les deux implementations qui SUBSISTENT, avec la raison de chacune.
#: ⚠️ Ce n'est pas une liste d'exemptions de confort : chaque entree porte un
#: motif VERIFIABLE, et `GU-6` exige que ce motif soit ecrit dans le code.
#: ⚠️⚠️ `a6._gini_lorenz` EST SORTIE DE CETTE LISTE LE 06/09/2026 (lot 4).
#: Elle y figurait pour DEUX raisons, et la mesure les a separees :
#:   · l'argument `expo` est une VRAIE methode, legitime -- il accumule le
#:     TAUX `y_true/expo` quand `y_true` est un comptage et `y_pred` un taux
#:     (correctif V15 #3). Effet mesure : **0,0213**. Il est CONSERVE, a la
#:     frontiere d'A6, comme `a3`/`a4`/`a5` gardent leur bornage ;
#:   · l'axe de population `linspace(0, 1, n)` etait un VRAI DEFAUT, biaise
#:     de **+1/n** systematiquement. Corrige : la formule vient du socle.
#: *Une fonction peut porter une vraie methode ET un vrai defaut ; les
#: separer demande de mesurer, pas de lire.*
_NON_DELEGUEES = {
    'core/conformite_reglementaire.py': (
        '_gini_trie_par',
        # ⚠️ Il trie par une COVARIABLE, pas par une prediction : c'est un
        # autre estimateur, et il decide des verdicts du controle anti-fuite.
        # Les ex aequo y sont massifs (une variable categorielle), donc le
        # traitement y compte DAVANTAGE -- raison de plus pour le mesurer
        # dans son propre lot plutot que de le changer en passant.
        'covariable'),
}


def _sans_ex_aequo(n=600, graine=5):
    rng = np.random.default_rng(graine)
    return rng.poisson(0.25, n).astype(float), rng.random(n)


def _avec_ex_aequo(n=600, paliers=6, graine=5):
    rng = np.random.default_rng(graine)
    return (rng.poisson(0.25, n).astype(float),
            rng.integers(0, paliers, n).astype(float) / paliers)


def _tri_simple(y, p, kind='mergesort', renverse=False):
    """Une des trois conventions d'avant, pour le SECOND SENS."""
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    ordre = (np.argsort(p, kind=kind)[::-1] if renverse
             else np.argsort(-p, kind=kind))
    ys = y[ordre]
    total = float(ys.sum())
    if total <= 0:
        return None
    trap = getattr(np, 'trapezoid', None) or np.trapz
    return float(2.0 * trap(np.cumsum(ys) / total,
                            np.arange(1, len(ys) + 1) / len(ys)) - 1.0)


class TestLaFormuleDuSocle(unittest.TestCase):

    def test_GU1_le_gini_du_socle_est_INVARIANT_PAR_PERMUTATION(self):
        """⚠️⚠️ LA PROPRIETE QUI DEFINIT UNE MESURE DU MODELE. Permuter les
        lignes du fichier ne change aucun risque : un Gini qui bouge mesure
        l'ordre du fichier, pas le modele."""
        rng = np.random.default_rng(11)
        y, p = _avec_ex_aequo(1200, paliers=5)
        valeurs = []
        for _ in range(6):
            idx = rng.permutation(len(y))
            valeurs.append(gini_lorenz(y[idx], p[idx]))
        etendue = max(valeurs) - min(valeurs)
        self.assertLess(
            etendue, 1e-12,
            f'le Gini du socle bouge de {etendue:.9f} quand on permute les '
            f'lignes : il mesure l ordre du fichier, pas le modele')

    def test_GU1b_SECOND_SENS_les_trois_anciens_tris_BOUGEAIENT(self):
        """⚠️ *Un controle qui ne rougit sur rien ne surveille rien.* Si les
        tris simples etaient eux aussi invariants, `GU-1` serait vrai sans
        rien devoir au traitement des ex aequo."""
        rng = np.random.default_rng(11)
        y, p = _avec_ex_aequo(1200, paliers=5)
        for libelle, kw in (('mergesort', {'kind': 'mergesort'}),
                            ('quicksort', {'kind': 'quicksort'}),
                            ('croissant renverse', {'kind': 'mergesort',
                                                    'renverse': True})):
            with self.subTest(tri=libelle):
                vals = []
                for _ in range(6):
                    idx = rng.permutation(len(y))
                    vals.append(_tri_simple(y[idx], p[idx], **kw))
                self.assertGreater(
                    max(vals) - min(vals), 1e-6,
                    f'le tri « {libelle} » est invariant par permutation : la '
                    f'fixture ne porte plus d ex aequo et GU-1 ne prouve rien')

    def test_GU1c_le_traitement_des_ex_aequo_rend_LE_TRI_INDIFFERENT(self):
        """⚠️⚠️ TROUVÉ PAR UN PLANT MUET. Le sceau a remplacé `mergesort` par
        `quicksort` dans le socle : **aucun contrôle n'a rougi**. Ce n'était
        pas un trou, c'était une PROPRIÉTÉ non énoncée — le regroupement
        remplace la cible par la moyenne du palier, et une moyenne ne dépend
        pas de l'ordre interne du groupe.

        *Un plant muet est soit un trou, soit une propriété qu'on n'avait pas
        écrite.* Celui-ci était la seconde ; elle est maintenant tenue.
        """
        y, p = _avec_ex_aequo(900, paliers=4)
        ref = gini_lorenz(y, p)

        def par_tri(kind):
            ordre = np.argsort(-p, kind=kind)
            yo, po = y[ordre], p[ordre]
            _, d, t = np.unique(-po, return_index=True, return_counts=True)
            lisse = np.empty_like(yo)
            for i, j in zip(d, t):
                lisse[i:i + j] = yo[i:i + j].mean()
            total = float(lisse.sum())
            trap = getattr(np, 'trapezoid', None) or np.trapz
            return float(2.0 * trap(np.cumsum(lisse) / total,
                                    np.arange(1, len(lisse) + 1) / len(lisse))
                         - 1.0)

        for kind in ('mergesort', 'quicksort', 'heapsort'):
            with self.subTest(tri=kind):
                self.assertAlmostEqual(
                    par_tri(kind), ref, places=12,
                    msg=f'le tri « {kind} » change le résultat : le '
                        f'regroupement par palier ne neutralise plus l ordre')

    def test_GU2_une_prediction_CONSTANTE_rend_ZERO(self):
        """⚠️⚠️ LE CAS MESURE SUR LE VRAI PORTEFEUILLE : `a3:cout_moyen`
        predit UNE valeur pour 2 500 contrats. Le vrai Gini est zero ; les
        trois conventions rendaient -0,000349, -0,000349 et +0,000349 --
        **de signes opposes**, tires de l'ordre du fichier."""
        rng = np.random.default_rng(3)
        y = rng.poisson(0.25, 800).astype(float)
        p = np.ones(800)
        self.assertAlmostEqual(
            gini_lorenz(y, p), 0.0, places=5,
            msg='un modele qui predit la MEME valeur pour tout le monde a un '
                'Gini non nul : il est fabrique a partir de l ordre des lignes')
        # ⚠️ Le second sens : un tri simple, lui, rend une valeur non nulle.
        self.assertGreater(
            abs(_tri_simple(y, p)), 1e-3,
            'le tri simple rend deja zero sur une prediction constante : ce '
            'test ne mesure plus l apport du traitement des ex aequo')

    def test_GU3_SANS_ex_aequo_il_COINCIDE_avec_un_tri_simple(self):
        """⚠️ *Le traitement des ex aequo ne doit rien changer quand il n'y en
        a pas.* Sinon l'unification deplacerait des chiffres sans raison."""
        y, p = _sans_ex_aequo(900)
        self.assertEqual(len(np.unique(p)), len(p), 'la fixture porte des ex '
                                                    'aequo : elle ne teste pas '
                                                    'ce qu elle annonce')
        self.assertAlmostEqual(gini_lorenz(y, p), _tri_simple(y, p), places=12)

    def test_GU7_le_contrat_d_absence_du_socle_est_intact(self):
        vide = np.array([])
        self.assertIsNone(gini_lorenz(vide, vide))
        self.assertIsNone(gini_lorenz(np.zeros(50), np.random.random(50)))
        self.assertIsNone(gini_lorenz(np.array([1.0]), np.array([1.0])))
        self.assertIsNone(gini_lorenz(np.zeros(10), np.zeros(9)))


class TestLesTroisAgentsSontDACCORD(unittest.TestCase):
    """⚠️⚠️ VERIFIE PAR EXECUTION, PAS PAR LECTURE. *Une delegation ecrite
    dans une docstring n'est pas une delegation tenue.*"""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        from direction_non_vie.tarification.a5_deep_learning.agent import (
            AgentA5DeepLearning,
        )
        cls.agents = {
            'a3': AgentA3GLM.__new__(AgentA3GLM)._calculer_gini,
            'a4': AgentA4ML.__new__(AgentA4ML)._calculer_gini,
            'a5': AgentA5DeepLearning.__new__(
                AgentA5DeepLearning)._calculer_gini,
        }

    def test_GU4_a3_a4_a5_rendent_EXACTEMENT_la_meme_valeur(self):
        rng = np.random.default_rng(7)
        y = rng.poisson(0.25, 800).astype(float)
        jeux = {'continues': rng.random(800),
                '8 paliers': rng.integers(0, 8, 800).astype(float) / 8.0,
                '3 paliers': rng.integers(0, 3, 800).astype(float),
                'constante': np.ones(800)}
        for libelle, p in jeux.items():
            with self.subTest(predictions=libelle):
                vals = {nom: f(y, p) for nom, f in self.agents.items()}
                self.assertEqual(
                    len(set(vals.values())), 1,
                    f'les trois agents rendent des Gini DIFFERENTS sur des '
                    f'predictions {libelle} : {vals}')
                self.assertAlmostEqual(
                    next(iter(vals.values())), gini_lorenz(y, p), places=12,
                    msg='les agents ne rendent pas la valeur du socle')

    def test_GU7b_l_absence_est_tenue_PAR_LE_SOCLE_et_les_gardes_locaux_sont_redondants(
            self):
        """⚠️⚠️ CE TEST S'APPELAIT « chaque frontiere GARDE son contrat », ET
        C'ETAIT FAUX — trouve par un plant muet. Le sceau a retire le garde
        `np.sum(y_true) == 0` d'A3 : **aucun controle n'a rougi**, parce que
        le socle rend `None` de lui-meme sur une cible de somme nulle. Le
        garde local est donc REDONDANT depuis la delegation.

        *Un test dont le nom attribue un resultat au mauvais mecanisme atteste
        sans surveiller.* Il verifie desormais ce qui est vrai : le RESULTAT
        est `None`, et c'est le socle qui le tient.
        """
        y0 = np.zeros(100)
        p = np.random.default_rng(1).random(100)
        # ⚠️ La source de verite, verifiee d'abord : c'est le socle.
        self.assertIsNone(gini_lorenz(y0, p))
        self.assertIsNone(gini_lorenz(np.array([]), np.array([])))
        for nom, f in self.agents.items():
            with self.subTest(agent=nom):
                self.assertIsNone(f(y0, p), f'{nom} ne rend plus None sur une '
                                            f'cible sans sinistre')
                self.assertIsNone(f(np.array([]), np.array([])))


class TestCeQuiRESTE(unittest.TestCase):
    """⚠️⚠️ *Nommer ce qu'un lot ne couvre pas vaut mieux que de laisser
    croire qu'il a tout pris.*"""

    @staticmethod
    def _corps(chemin, nom):
        """Rend `(instructions, segment_complet)`.

        ⚠️⚠️ DEUX EXTRACTIONS, ET IL EN FALLAIT DEUX -- `GU-6` a echoue sur sa
        premiere version pour cette raison exacte. `ast.get_source_segment`
        applique aux INSTRUCTIONS ne rend que du code execute : c'est ce qu'il
        faut pour chercher `cumsum` sans se faire piéger par une docstring qui
        DECRIT le critere. Mais **les commentaires ne sont pas des noeuds
        AST** : ils disparaissent de cette extraction. Un controle qui exige
        qu'un motif soit ECRIT dans le code doit donc lire le segment COMPLET.
        *Un relevé qui ne traverse pas ce qu'il cherche conclut toujours a
        l'absence.*
        """
        source = pathlib.Path(_RACINE, chemin).read_text(encoding='utf-8')
        for n in ast.walk(ast.parse(source)):
            if isinstance(n, ast.FunctionDef) and n.name == nom:
                instructions = list(n.body)
                if (instructions and isinstance(instructions[0], ast.Expr)
                        and isinstance(instructions[0].value, ast.Constant)
                        and isinstance(instructions[0].value.value, str)):
                    instructions = instructions[1:]
                return ('\n'.join(ast.get_source_segment(source, i) or ''
                                  for i in instructions),
                        ast.get_source_segment(source, n) or '')
        return None, ''

    def test_GU5_a3_a4_a5_ne_CALCULENT_plus(self):
        """⚠️ Releve AST : leur corps, docstring retiree, n'emploie plus
        `cumsum`. *Une delegation se verifie, elle ne se declare pas.*"""
        _base = 'direction_non_vie/tarification'
        for chemin in (f'{_base}/a3_glm/agent.py',
                       f'{_base}/a4_ml/agent.py',
                       f'{_base}/a5_deep_learning/agent.py'):
            with self.subTest(agent=chemin):
                corps, _ = self._corps(chemin, '_calculer_gini')
                self.assertIsNotNone(corps, f'{chemin} : `_calculer_gini` a '
                                            f'disparu')
                self.assertNotIn(
                    'cumsum', corps,
                    f'{chemin} recalcule une courbe de Lorenz au lieu de '
                    f'deleguer au socle : la duplication est revenue')
                self.assertIn('gini_socle', corps,
                              f'{chemin} n appelle pas le socle')

    def test_GU6_les_NON_DELEGUEES_sont_nommees_ET_motivees(self):
        """⚠️⚠️ Deux implementations subsistent. Chacune doit porter SA raison
        DANS LE CODE -- pas seulement dans un rapport que personne ne relira.
        Et le motif doit etre VRAI : on verifie le marqueur qui le fonde."""
        for chemin, (nom, marqueur) in _NON_DELEGUEES.items():
            with self.subTest(implementation=f'{chemin}::{nom}'):
                corps, complet = self._corps(chemin, nom)
                self.assertIsNotNone(corps, f'{chemin}::{nom} a disparu -- si '
                                            f'elle a ete deleguee, retirer '
                                            f'cette entree')
                # ⚠️ `cumsum` sur les INSTRUCTIONS : une docstring qui decrit
                # le critere ne doit pas suffire a passer.
                self.assertIn(
                    'cumsum', corps,
                    f'{chemin}::{nom} ne calcule plus : elle a ete deleguee '
                    f'sans que cette liste soit mise a jour')
                # ⚠️ Le motif sur le segment COMPLET : il vit dans un
                # commentaire, et un commentaire n'est pas un noeud AST.
                self.assertIn(
                    marqueur, complet,
                    f'{chemin}::{nom} ne porte plus le motif « {marqueur} » '
                    f'qui justifie qu elle reste distincte')

    def test_GU9_a6_DELEGUE_mais_GARDE_sa_normalisation_par_l_exposition(self):
        """⚠️⚠️ LES DEUX FACES DU LOT 4, DANS UN SEUL TEST.

        `a6._gini_lorenz` portait une VRAIE methode (`expo`) et un VRAI defaut
        (l'axe `linspace`, biaise de +1/n). La formule descend au socle ; la
        normalisation reste. *Le socle rend la formule, l'agent garde sa
        methode.*
        """
        from direction_non_vie.tarification.a6_comparaison.agent import (
            AgentA6Comparaison,
        )
        f = AgentA6Comparaison.__dict__['_gini_lorenz'].__func__
        corps, complet = TestCeQuiRESTE._corps(
            'direction_non_vie/tarification/a6_comparaison/agent.py',
            '_gini_lorenz')
        self.assertNotIn(
            'cumsum', corps,
            "`a6._gini_lorenz` recalcule une courbe de Lorenz au lieu de "
            "deleguer : l axe biaise peut etre revenu avec elle")
        self.assertIn('gini_socle', corps, "`a6` n appelle pas le socle")
        self.assertIn('expo', corps,
                      "`a6` a perdu sa normalisation par l exposition : "
                      "c'etait une VRAIE methode, pas une divergence")
        self.assertIn('0,0213', complet,
                      "l effet mesure de l exposition n est plus publie a cote "
                      "de la methode qu il justifie")

        # ⚠️ ET ON LE VERIFIE PAR EXECUTION, pas seulement au texte.
        rng = np.random.default_rng(5)
        n = 800
        y = rng.poisson(0.3, n).astype(float)
        p = rng.random(n)
        expo = rng.uniform(0.2, 1.0, n)
        avec, sans = f(y, p, expo=expo), f(y, p, expo=None)
        self.assertIsNotNone(avec)
        self.assertNotAlmostEqual(
            avec, sans, places=4,
            msg="l exposition ne change plus rien : la normalisation a ete "
                "perdue en cours de delegation")
        # ⚠️ Et la valeur EST celle du socle sur l observation normalisee.
        attendu = gini_lorenz(y / np.maximum(expo, 1e-9), p)
        self.assertAlmostEqual(avec, round(float(attendu), 4), places=4)

    def test_GU10_l_axe_de_population_n_est_plus_BIAISE(self):
        """⚠️⚠️ LE DEFAUT, MESURE ET FERME. `linspace(0, 1, n)` associe la
        premiere valeur cumulee -- qui couvre deja 1/n de la population -- a
        la fraction ZERO. Sur un modele SANS pouvoir discriminant, le vrai
        Gini est zero ; l ancien axe rendait **+1/n** en moyenne."""
        from direction_non_vie.tarification.a6_comparaison.agent import (
            AgentA6Comparaison,
        )
        f = AgentA6Comparaison.__dict__['_gini_lorenz'].__func__
        trap = getattr(np, 'trapezoid', None) or np.trapz

        def ancien(y, p):
            ys = np.asarray(y, float)[np.argsort(-np.asarray(p, float))]
            return float(2 * trap(np.cumsum(ys) / ys.sum(),
                                  np.linspace(0, 1, len(ys))) - 1)

        rng = np.random.default_rng(3)
        n, reps = 300, 150
        actuels, anciens = [], []
        for _ in range(reps):
            y = rng.poisson(0.3, n).astype(float)
            p = rng.random(n)
            if y.sum() <= 0:
                continue
            v = f(y, p)
            if v is None:
                continue
            actuels.append(v)
            anciens.append(ancien(y, p))
        # ⚠️⚠️ ON MESURE L'ECART, PAS LA MOYENNE ABSOLUE. Ma premiere version
        # exigeait `|moyenne| < 1,2/n` sur 150 tirages : l'erreur-type du Gini
        # sur un modele nul y est du meme ordre que le biais cherche, donc le
        # test rougissait sur du BRUIT. A donnee fixee, en revanche, l'ecart
        # entre les deux axes est DETERMINISTE -- c'est lui qui vaut 1/n, et
        # il se mesure sans bruit. *Quand un estimateur est bruite, comparer
        # deux estimateurs sur LES MEMES tirages retire le bruit commun.*
        ecarts = np.asarray(anciens) - np.asarray(actuels)
        moyen = float(ecarts.mean())
        self.assertGreater(
            moyen, 0.5 / n,
            f'l ancien axe ne montre plus de biais (ecart moyen {moyen:.6f}) : '
            f'cette fixture ne mesure plus rien')
        self.assertLess(
            abs(moyen - 1.0 / n), 0.35 / n,
            f'le biais de l ancien axe vaut {moyen:.6f} au lieu de '
            f'{1.0 / n:.6f} = 1/n : la forme du defaut a change, la prose qui '
            f'l explique doit etre relue')
        # ⚠️ ET LE SENS : l'ancien SUR-estimait toujours.
        self.assertGreater(
            float((ecarts > 0).mean()), 0.95,
            'l ancien axe ne sur-estimait pas systematiquement : le defaut '
            'decrit dans la prose n est pas celui que ce test mesure')

    def test_GU11_le_contrat_publie_d_a6_est_INTACT(self):
        """⚠️ La delegation porte la formule, pas le contrat : `None` quand la
        prediction est constante, et l arrondi a 4 decimales."""
        from direction_non_vie.tarification.a6_comparaison.agent import (
            AgentA6Comparaison,
        )
        f = AgentA6Comparaison.__dict__['_gini_lorenz'].__func__
        rng = np.random.default_rng(9)
        y = rng.poisson(0.3, 400).astype(float)
        self.assertIsNone(f(y, np.ones(400)),
                          'une prediction CONSTANTE ne rend plus None')
        self.assertIsNone(f(np.zeros(400), rng.random(400)),
                          'une cible sans sinistre ne rend plus None')
        v = f(y, rng.random(400))
        self.assertIsNotNone(v)
        self.assertEqual(round(v, 4), v, "l arrondi a 4 decimales a disparu")

    def test_GU6b_le_compte_des_implementations_est_CELUI_MESURE(self):
        """⚠️ On re-derive le compte plutot que de croire la liste."""
        implementations = []
        for chemin in sorted(pathlib.Path(_RACINE).rglob('*.py')):
            s = chemin.as_posix()
            if ('.venv' in s or '/audit_2026_08/' in s
                    or chemin.name.startswith('test_')):
                continue
            source = chemin.read_text(encoding='utf-8', errors='replace')
            try:
                arbre = ast.parse(source)
            except SyntaxError:                     # pragma: no cover
                continue
            for n in ast.walk(arbre):
                if not (isinstance(n, ast.FunctionDef)
                        and 'gini' in n.name.lower()):
                    continue
                corps = list(n.body)
                if (corps and isinstance(corps[0], ast.Expr)
                        and isinstance(corps[0].value, ast.Constant)
                        and isinstance(corps[0].value.value, str)):
                    corps = corps[1:]
                code = '\n'.join(ast.get_source_segment(source, i) or ''
                                 for i in corps)
                if 'cumsum' in code:
                    implementations.append(f'{s}::{n.name}')
        self.assertEqual(
            len(implementations), 1 + len(_NON_DELEGUEES),
            f'le depot compte {len(implementations)} implementations de Gini, '
            f'la liste en declare {1 + len(_NON_DELEGUEES)} (le socle plus les '
            f'non-deleguees) : {sorted(implementations)}')
        self.assertTrue(
            any(c.endswith('core/validation_tarif.py::gini_lorenz')
                for c in implementations),
            "le Gini canonique du socle n'est plus une implementation")


if __name__ == '__main__':
    unittest.main(verbosity=2)
