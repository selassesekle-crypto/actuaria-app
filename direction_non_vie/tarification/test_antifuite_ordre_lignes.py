# -*- coding: utf-8 -*-
"""LE GARDE-FOU ANTI-FUITE RENDAIT UN VERDICT QUI DEPENDAIT DE L'ORDRE DU
FICHIER (lot 5).

`detecter_fuites_par_effet` decide `signal = max(spearman, gini_normalise)`
contre un seuil de 0,80. Le second terme passait par `_gini_trie_par`, qui
triait la cible par une COVARIABLE avec `np.argsort(-x)` -- **sans traiter les
EX AEQUO**. Or trier par une covariable categorielle met des groupes entiers a
egalite : l'ordre A L'INTERIEUR d'un palier vient alors du fichier, et il
change le resultat.

⚠️⚠️ CE QUE CA COUTE, MESURE LE 06/09/2026. Sur `auto` (3 000 lignes, cible
`nb_sinistres` a 4 valeurs distinctes = **100 % d'ex aequo**) :

    `antecedents_sinistres_n1` (4 modalites) : `g_norm` 0,0089 -> 0,0421
                                               facteur 4,8, l'actuel
                                               SOUS-ESTIME
    etendue sur 8 permutations des MEMES lignes :
        4 modalites    : 0,048864   (socle : 0,000000)
        11 modalites   : 0,005232   (socle : 0,000000)
        2 848 modalites: 0,000726   (socle : 0,000000)

*L'etendue croit quand les modalites diminuent : c'est la signature exacte de
l'effet ex aequo.*

⚠️⚠️ ET LE VERDICT LUI-MEME BASCULE. Aucune des 18 fixtures du referentiel ne
couvre la zone qui decide -- leurs signaux plafonnent a 0,35 pour un seuil a
0,80, marge minimale 0,45. On PLANTE donc des fuites calibrees dans la bande,
et on permute les lignes. Six fuites, 40 ordres chacune :

    formule ACTUELLE : 4/40, 36/40, 29/40, 5/40, 35/40, 4/40 detectees
    formule SOCLE    : 0/40, 40/40, 40/40, 0/40, 40/40, 0/40

**Le socle est toujours 0/40 ou 40/40 ; l'actuel est entre les deux dans les
six cas.** Sur un garde-fou de protection des donnees personnelles, le meme
portefeuille range dans un autre ordre pouvait etre declare << fuite
detectee >> ou << aucune fuite >>.

⚠️ CE N'EST PAS UNE QUESTION DE VALEUR MOYENNE. Dans la bande, l'ecart entre
les deux formules vaut ~±0,01 SANS direction garantie -- j'ai mesure des cas
ou le socle est AU-DESSOUS de l'actuel. Ce qui change, c'est que l'un est
DETERMINE et l'autre non.

Ce que cette sentinelle exige :
  AF-1  une fuite FRANCHE est attrapee -- et un temoin de bruit pur ne l'est
        jamais ;
  AF-2  ⚠️ le `g_norm` d'une variable CATEGORIELLE est INVARIANT par
        permutation des lignes ;
  AF-3  ⚠️⚠️ le VERDICT d'une fuite calibree dans la bande est invariant par
        permutation -- dans les DEUX sens (une fuite au-dessus du seuil est
        toujours vue, une variable en dessous ne l'est jamais) ;
  AF-4  le denominateur `gini_parfait` ne change pas : trier la cible par
        elle-meme rend le lissage identite ;
  AF-5  la fixture TRAVERSE bien la zone qui decide : `rho` sous le seuil,
        donc c'est `g_norm` qui tranche.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""
import logging
import os
import sys
import unittest
import warnings

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

import numpy as np
import pandas as pd

from core.conformite_reglementaire import (
    SEUIL_CORRELATION_FUITE,
    detecter_fuites_par_effet,
)
from core.plan_tarifaire import PlanTarifaire

#: ⚠️ Aucun de ces noms ne doit porter un marqueur d'anteriorite : sinon la
#: variable part dans `signaux_experience` et on testerait l'autre branche.
_COL_FRANCHE = 'colonne_suspecte_franche'
_COL_BANDE = 'colonne_suspecte_bande'
_COL_TEMOIN = 'colonne_temoin_bruit'


def _portefeuille():
    from direction_non_vie.tarification import test_plan_invariants as T
    plan = PlanTarifaire.depuis_yaml(
        os.path.join(_RACINE, 'plans', 'auto.yaml'))
    np.random.seed(7)
    return plan, T.portefeuille_auto(3000, 1)


def _fuite_calibree(y_arr, graine, fraction):
    """Une fuite BINAIRE diluee, calibree pour tomber dans la bande du seuil.

    ⚠️ Binaire = 2 modalites = ex aequo massifs. C'est le seul regime ou la
    formule d'origine devenait indeterminee, et c'est donc le seul qui
    exerce la zone qui decide.
    """
    rng = np.random.default_rng(graine)
    x = (y_arr >= 1).astype(float).copy()
    idx = rng.choice(len(x), int(fraction * len(x)), replace=False)
    x[idx] = rng.integers(0, 2, len(idx)).astype(float)
    return x


def _controle(df, colonnes, cible):
    """⚠️⚠️ ON PASSE PAR LE CODE DE PRODUCTION, JAMAIS PAR UNE COPIE.

    Ma premiere version de ce fichier recalculait `g_norm` a cote, avec le
    socle -- elle aurait donc ete VERTE avant meme la delegation, en testant
    mon propre helper au lieu du garde-fou. *Un controle qui reconstruit ce
    qu'il pretend surveiller atteste sans surveiller.*
    """
    return detecter_fuites_par_effet(df, list(colonnes), cible)


def _g_norm_publie(df, colonne, cible, feats):
    """Le `gini_normalise` que le CONTROLE publie, ou `None` s'il ne signale
    pas la colonne (elle est alors sous le seuil)."""
    fuites = _controle(df, [*feats, colonne], cible)
    bloc = fuites.get(colonne)
    return None if bloc is None else bloc.get('gini_normalise')


def _rho(y_serie, x_serie):
    """Le Spearman du controle, a l'identique -- `nan` vaut zero.

    ⚠️ Le code de production ecrit `r != r` pour tester `nan` ; ici on emploie
    `math.isnan`, qui dit la meme chose sans le detour.
    """
    import math
    r = float(y_serie.rank().corr(x_serie.rank()))
    return 0.0 if math.isnan(r) else abs(r)


class TestFuitePlantee(unittest.TestCase):
    """⚠️⚠️ AUCUNE DES 18 FIXTURES NE COUVRE LA ZONE QUI DECIDE. On plante."""

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)
        cls.plan, cls.df = _portefeuille()
        cls.cible = cls.plan.cible_frequence
        cls.y = cls.df[cls.cible].astype(float)
        cls.y_arr = cls.y.to_numpy()
        rng = np.random.default_rng(11)
        cls.franche = (cls.y_arr >= 1).astype(float)
        cls.bruit = rng.random(len(cls.y_arr))
        # ⚠️ Calibree : `rho` SOUS le seuil, `g_norm` AU-DESSUS -- mesure du
        # 06/09/2026 (graine 21, 18 % de lignes brouillees).
        cls.bande = _fuite_calibree(cls.y_arr, 21, 0.18)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def _feats(self, df):
        return [f.nom for f in self.plan.facteurs
                if f.nom in df.columns
                and pd.api.types.is_numeric_dtype(df[f.nom])]

    def _df_avec(self, colonne, valeurs, permutation=None):
        df2 = self.df.copy()
        df2[colonne] = valeurs
        if permutation is not None:
            df2 = df2.iloc[permutation].reset_index(drop=True)
        return df2

    def test_AF5_la_fixture_TRAVERSE_la_zone_ou_g_norm_decide(self):
        """⚠️⚠️ *Une fixture doit prouver qu'elle traverse ce qu'elle mesure.*
        Si `rho` depassait deja le seuil, le verdict ne dependrait pas de
        `g_norm` et tout ce fichier serait vert sans rien avoir mesure."""
        s = pd.Series(self.bande, index=self.df.index)
        rho = _rho(self.y, s)
        self.assertLess(
            rho, SEUIL_CORRELATION_FUITE,
            f'la fuite calibree a un Spearman de {rho:.4f}, deja au-dessus du '
            f'seuil : c est `rho` qui decide, pas `g_norm` -- cette fixture '
            f'n exerce plus la zone que le lot corrige')
        # ⚠️ Et le `g_norm` PUBLIE par le controle doit dominer `rho`.
        df2 = self._df_avec(_COL_BANDE, self.bande)
        g = _g_norm_publie(df2, _COL_BANDE, self.cible, self._feats(df2))
        self.assertIsNotNone(
            g, 'la fuite calibree n est plus signalee du tout : elle est '
               'sortie de la bande du seuil')
        self.assertGreater(
            g, rho,
            f'`g_norm` ({g}) ne domine pas `rho` ({rho:.4f}) : le terme que '
            f'ce lot change ne decide pas de ce verdict')
        self.assertEqual(len(np.unique(self.bande)), 2,
                         'la fuite calibree n est plus binaire : sans ex '
                         'aequo massifs, il n y a rien a mesurer')

    def test_AF1_une_fuite_FRANCHE_est_attrapee_et_le_bruit_JAMAIS(self):
        """⚠️ Les deux sens. *Un controle qui signale tout ne signale rien.*"""
        df2 = self.df.copy()
        df2[_COL_FRANCHE] = self.franche
        df2[_COL_TEMOIN] = self.bruit
        feats = [f.nom for f in self.plan.facteurs
                 if f.nom in df2.columns
                 and pd.api.types.is_numeric_dtype(df2[f.nom])]
        fuites = detecter_fuites_par_effet(
            df2, [*feats, _COL_FRANCHE, _COL_TEMOIN], self.cible)
        self.assertIn(
            _COL_FRANCHE, fuites,
            'une colonne qui vaut 1 des que la cible est non nulle n est PAS '
            'signalee comme fuite : le garde-fou ne protege plus rien')
        self.assertNotIn(
            _COL_TEMOIN, fuites,
            'du BRUIT PUR est signale comme une fuite : le controle crierait '
            'sur tout, donc sur rien')

    def test_AF2_le_g_norm_d_une_CATEGORIELLE_est_invariant_par_permutation(
            self):
        """⚠️⚠️ LE DEFAUT, A LA RACINE. Permuter les lignes d'un fichier ne
        change aucun risque : un `g_norm` qui bouge mesure l'ordre du
        fichier."""
        rng = np.random.default_rng(1)
        valeurs = []
        for _ in range(8):
            p = rng.permutation(len(self.y_arr))
            df2 = self._df_avec(_COL_FRANCHE, self.franche, permutation=p)
            # ⚠️ La fuite FRANCHE est toujours signalee, donc son `g_norm`
            # est TOUJOURS observable dans la sortie du controle -- c'est ce
            # qui permet de le lire sans reconstruire le calcul.
            valeurs.append(
                _g_norm_publie(df2, _COL_FRANCHE, self.cible, self._feats(df2)))
        self.assertNotIn(None, valeurs,
                         'la fuite franche cesse d etre signalee sur certaines '
                         'permutations : le verdict lui-meme est instable')
        etendue = max(valeurs) - min(valeurs)
        self.assertLess(
            etendue, 1e-9,
            f'`g_norm` varie de {etendue:.6f} selon l ordre des lignes : le '
            f'garde-fou anti-fuite mesure le fichier, pas la variable')

    def test_AF3_le_VERDICT_d_une_fuite_de_la_BANDE_ne_depend_pas_de_l_ordre(
            self):
        """⚠️⚠️ LE POINT QUI COMPTE POUR UN GARDE-FOU RGPD. Mesure du
        06/09/2026 sur la formule d'origine : six fuites calibrees, 40 ordres
        chacune, verdicts **4/40, 36/40, 29/40, 5/40, 35/40, 4/40**. Le meme
        portefeuille range autrement changeait de verdict.

        ⚠️ Les DEUX sens : une fuite au-dessus du seuil doit etre vue a chaque
        fois, et une variable en dessous ne doit jamais l'etre.
        """
        # ⚠️⚠️ VINGT PERMUTATIONS, ET LE NOMBRE EST MESURE. Ma premiere version
        # en faisait HUIT : sur une fuite que la formule d'origine detectait
        # 36 fois sur 40, la probabilite de voir les DEUX verdicts n'etait que
        # de ~57 % -- le test rougissait a pile ou face. *Un controle qui
        # n'attrape le defaut qu'une fois sur deux n'est pas un controle.*
        # A 20 tirages sur la calibration la plus equilibree (29/40), elle
        # depasse 99,9 %.
        for graine, fraction, attendu in ((11, 0.19, True),
                                          (21, 0.18, True),
                                          (4, 0.18, False)):
            with self.subTest(graine=graine, fraction=fraction):
                x = _fuite_calibree(self.y_arr, graine, fraction)
                rng = np.random.default_rng(2)
                verdicts = set()
                for _ in range(20):
                    p = rng.permutation(len(self.y_arr))
                    df2 = self._df_avec(_COL_BANDE, x, permutation=p)
                    fuites = _controle(df2, [*self._feats(df2), _COL_BANDE],
                                       self.cible)
                    verdicts.add(_COL_BANDE in fuites)
                self.assertEqual(
                    len(verdicts), 1,
                    f'le verdict anti-fuite BASCULE selon l ordre des lignes '
                    f'(graine {graine}, {fraction:.0%} brouille) : sur un '
                    f'garde-fou de donnees personnelles, le meme portefeuille '
                    f'serait declare avec ou sans fuite selon son rangement')
                self.assertEqual(
                    verdicts.pop(), attendu,
                    f'le verdict a change de cote pour la fuite (graine '
                    f'{graine}) : la calibration de la fixture est perimee, '
                    f'ou le seuil a bouge')

    def test_AF4_le_DENOMINATEUR_ne_bouge_pas(self):
        """⚠️ `gini_parfait` trie la cible PAR ELLE-MEME : dans chaque palier
        d'ex aequo, tous les membres portent la MEME valeur, donc la somme
        cumulee est identique quel que soit l'ordre interne. Mesure sur les 18
        plans : ecart 0,000000 partout.

        ⚠️⚠️ ET C'EST VRAI **AVANT COMME APRES** LA DELEGATION -- verifie par
        un plant reste MUET. Ce test ne surveille donc PAS ce lot : il fige
        une propriete qui explique pourquoi seul le NUMERATEUR bougeait. *Le
        dire vaut mieux que de le laisser passer pour un garde-fou actif.*
        Il reprendrait du service si quelqu'un changeait la definition du
        denominateur.
        """
        from core.validation_tarif import gini_lorenz
        rng = np.random.default_rng(5)
        parfaits = []
        for _ in range(8):
            p = rng.permutation(len(self.y_arr))
            parfaits.append(gini_lorenz(self.y_arr[p], self.y_arr[p]))
        self.assertLess(
            max(parfaits) - min(parfaits), 1e-12,
            'le denominateur `gini_parfait` depend de l ordre des lignes : '
            'tout `g_norm` en herite')


if __name__ == '__main__':
    unittest.main(verbosity=2)
