r"""
==============================================================================
  UN MODELE AJUSTE SAIT PREDIRE SUR LA MATRICE QU'ON LUI DONNERA
==============================================================================

⚠️⚠️ CE QUE CE CONTROLE EXISTE POUR EMPECHER, ET IL EST ARRIVE PENDANT HUIT
JOURS. `core.frequence._matrice` avait DEUX ecritures du meme geste : avec
colonnes, `add_constant(df[cols], has_constant='add')` ; sans colonne, une
colonne `intercept` de uns PUIS `add_constant(..., has_constant='add')`,
qui en ajoutait une SECONDE.

    _matrice(df, ['x1','x2'])   ->  (n, 3)  ['const','x1','x2']
    _matrice(df, [])            ->  (n, 2)  ['const','intercept']
    ce que l'appelant bati      ->  (n, 1)  ['const']

L'ajustement portait DEUX parametres, la prediction n'offrait QU'UNE
colonne : `ValueError: shapes (500,1) and (2,) not aligned`.

MESURE DU 13/09/2026, gate complete : le repli a tire **7 fois**, il a
produit **6 desaccords**, et **DEUX seulement** etaient visibles. *Quatre
etaient absorbes en silence par des tests qui n'exigeaient rien des
metriques.*

⚠️⚠️ ET LES DEUX COLONNES ETAIENT DES UNS CONTRE DES UNS -- la matrice
etait COLINEAIRE avec sa propre constante. La pseudo-inverse coupait
l'intercept en deux moities arbitraires : mesure, `-2,3026` devenait
`-1,1509` et `-1,1509`. *Le predicteur lineaire ne bouge pas ; les
COEFFICIENTS PUBLIES si* -- et ce sont eux que le rapport signe montre.

⚠️ LE DEFAUT VENAIT D'UN REFACTOR QUI ANNONCAIT << mot pour mot >>
(`a82f450`, 05/09) : il a pose `has_constant='add'` sur les DEUX branches,
alors qu'une seule en avait besoin. *La cause profonde n'est pas le
parametre : c'est qu'un meme geste etait ecrit DEUX FOIS.*

CE QUE CES CONTROLES SURVEILLENT : le COMPORTEMENT -- un modele ajuste
sait-il predire sur la matrice que son appelant construit ? Ils ne
verifient jamais qu'une branche est absente : une reecriture correcte doit
rester verte, et toute divergence future, quelle qu'en soit la forme, doit
rougir.
==============================================================================
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest
import warnings

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

import numpy as np
import pandas as pd
import statsmodels.api as sm

from core.frequence import _matrice, ajuster_glm_frequence

#: le seuil que l'appelant qui SELECTIONNE detient (`a3_glm.SEUIL_PVALUE`)
_SEUIL = 0.05


def _jeu(n=200, graine=11, colonnes=2):
    """⚠️ UN INDEX NON TRIVIAL : si une construction perdait l'index, la
    cible et l'offset cesseraient de s'aligner -- un defaut pire que celui
    qu'on surveille, et invisible sur un index par defaut."""
    r = np.random.default_rng(graine)
    d = pd.DataFrame(index=pd.RangeIndex(1000, 1000 + n))
    for i in range(colonnes):
        d[f'x{i + 1}'] = r.normal(size=n)
    d['nb'] = r.poisson(0.3, n).astype(float)
    d['expo'] = np.clip(r.uniform(0.3, 1.0, n), 0.05, 1.0)
    return d


def _offset(d):
    return np.log(np.asarray(d['expo'], dtype=float))


def _matrice_de_l_appelant(d, colonnes):
    """⚠️ LE GESTE DE L'APPELANT, ECRIT ICI COMME IL L'ECRIT. C'est la
    reference : un modele doit savoir predire SUR CETTE MATRICE-LA."""
    return sm.add_constant(d[colonnes].fillna(0), has_constant='add')


class TestAjustementEtPredictionSAccordent(unittest.TestCase):

    def setUp(self):
        warnings.filterwarnings('ignore')

    def test_MAT1_SCEAU_le_modele_predit_sur_la_matrice_de_l_appelant(self):
        """⚠️⚠️ LE SCEAU, ET IL PORTE SUR LES TROIS TAILLES. Le defaut ne
        vivait que sur la taille ZERO ; ne tester que celle-la fermerait
        l'occurrence en laissant la classe ouverte. *Une divergence peut
        naitre demain sur n'importe quelle taille.*"""
        for k in (2, 1, 0):
            with self.subTest(colonnes=k):
                d = _jeu(colonnes=max(k, 1))
                cols = [f'x{i + 1}' for i in range(k)]
                res = ajuster_glm_frequence(d, cols, 'nb', _offset(d))
                X = _matrice_de_l_appelant(d, cols)
                try:
                    pred = res['modele'].predict(X, offset=_offset(d))
                except Exception as e:                        # noqa: BLE001
                    self.fail(
                        f"{k} colonne(s) : le modele ajuste ne sait pas "
                        f"predire sur la matrice que l'appelant construit "
                        f"-- {type(e).__name__}: {e}. C'est le defaut du "
                        f"13/09, revenu.")
                p = np.asarray(pred, dtype=float)
                self.assertTrue(
                    np.all(np.isfinite(p)) and np.all(p > 0),
                    f"{k} colonne(s) : la frequence predite n'est pas "
                    f"finie et positive")
        print("    MAT-1 SCEAU : 2, 1 et 0 colonne(s) -- le modele predit "
              "sur la matrice de l'appelant")

    def test_MAT2_SCEAU_autant_de_parametres_que_de_COLONNES(self):
        """⚠️⚠️ LA CAUSE, PAS LE SYMPTOME. Un parametre de plus que de
        colonnes signifie une constante DUPLIQUEE, donc une matrice
        colineaire avec elle-meme -- et des coefficients publies coupes en
        moities arbitraires."""
        for k in (2, 1, 0):
            with self.subTest(colonnes=k):
                d = _jeu(colonnes=max(k, 1))
                cols = [f'x{i + 1}' for i in range(k)]
                M = _matrice(d, cols)
                res = ajuster_glm_frequence(d, cols, 'nb', _offset(d))
                self.assertEqual(
                    len(res['modele'].params), M.shape[1],
                    f"{k} colonne(s) : {len(res['modele'].params)} "
                    f"parametre(s) pour {M.shape[1]} colonne(s).")
                self.assertEqual(
                    M.shape[1], k + 1,
                    f"{k} colonne(s) + la constante devraient faire "
                    f"{k + 1} colonnes, la matrice en a {M.shape[1]} : "
                    f"{list(M.columns)}")
                #: ⚠️ ET AUCUNE COLONNE EN DOUBLE : deux colonnes de uns
                #: passeraient le compte si l'une remplacait une vraie.
                vues = [tuple(np.asarray(M[c], dtype=float))
                        for c in M.columns]
                self.assertEqual(
                    len(set(vues)), len(vues),
                    f"{k} colonne(s) : deux colonnes IDENTIQUES dans la "
                    f"matrice de conception -- {list(M.columns)}")
        print("    MAT-2 SCEAU : un parametre par colonne, aucune colonne "
              "en double")

    def test_MAT3_SCEAU_le_chemin_du_REPLI_par_epuisement_predit_aussi(self):
        """⚠️⚠️ LE CHEMIN EXACT DES DEUX ROUGES DE LA GATE. On n'arrive pas
        a l'intercept seul en le demandant : on y tombe quand la selection
        descendante RETIRE toutes les variables. Sur du bruit pur, aucune
        p-value ne passe le seuil, et le repli se declenche pour de vrai.

        *Un controle qui appellerait avec une liste vide testerait la porte
        d'entree, pas le chemin qui a echoue.*"""
        r = np.random.default_rng(23)
        n = 300
        d = pd.DataFrame(index=pd.RangeIndex(500, 500 + n))
        #: du bruit pur : aucune variable n'explique la cible
        for i in range(4):
            d[f'x{i + 1}'] = r.normal(size=n)
        #: ⚠️ DES SINISTRES, MEME PEU. Une cible entierement NULLE rend
        #: l'ajustement Poisson degenere (`deviance returned a nan`) : le
        #: controle echouerait sur son FIXTURE et non sur le code.
        d['nb'] = r.poisson(0.25, n).astype(float)
        d['expo'] = np.full(n, 0.7)
        cols = [f'x{i + 1}' for i in range(4)]
        res = ajuster_glm_frequence(d, cols, 'nb', _offset(d),
                                    selection=True, seuil_pvalue=_SEUIL)
        self.assertEqual(
            res['variables'], [],
            "la selection n'a pas epuise les variables : ce controle ne "
            "mesure pas le chemin du repli")
        X = _matrice_de_l_appelant(d, res['variables'])
        try:
            pred = res['modele'].predict(X, offset=_offset(d))
        except Exception as e:                                # noqa: BLE001
            self.fail(
                f"le chemin du REPLI ne sait pas predire -- "
                f"{type(e).__name__}: {e}. C'est exactement le rouge de la "
                f"gate du 13/09.")
        #: ⚠️ PREDIRE NE SUFFIT PAS : une prediction qui rendrait des `nan`
        #: passerait le `try` et ne vaudrait rien.
        p = np.asarray(pred, dtype=float)
        self.assertTrue(
            np.all(np.isfinite(p)) and np.all(p > 0),
            'le repli predit, mais sa frequence n est pas finie et positive')
        self.assertEqual(len(res['modele'].params), 1,
                         'le modele du repli porte plus d un parametre')
        print(f"    MAT-3 SCEAU : repli par epuisement de {len(cols)} "
              f"variables -> predit, {len(res['modele'].params)} parametre")

    def test_MAT4_SCEAU_l_INTERCEPT_publie_n_est_pas_coupe_en_deux(self):
        """⚠️⚠️ CE QU'UN ACTUAIRE LIT. Une constante dupliquee ne change pas
        le predicteur lineaire -- elle coupe le COEFFICIENT PUBLIE en
        moities arbitraires. Mesure du 13/09 : `-2,3026` devenait `-1,1509`
        et `-1,1509`. *Le prix ne bougeait pas ; le rapport signe, si.*"""
        d = _jeu(colonnes=1)
        res = ajuster_glm_frequence(d, [], 'nb', _offset(d))
        params = dict(res['modele'].params)
        self.assertEqual(
            len(params), 1,
            f"le modele a intercept seul publie {len(params)} "
            f"coefficients : {params}")
        #: ⚠️ ET LA VALEUR EST CELLE D'UN INTERCEPT ENTIER, pas d'une
        #: moitie : on la recompose depuis la frequence observee.
        seul = float(next(iter(params.values())))
        attendu = float(np.log(
            d['nb'].sum() / np.exp(_offset(d)).sum()))
        self.assertAlmostEqual(
            seul, attendu, places=6,
            msg=f"l'intercept publie ({seul}) n'est pas le logarithme de la "
                f"frequence observee ({attendu}) : il a ete reparti.")
        print(f"    MAT-4 SCEAU : un seul coefficient, {seul:.6f} = "
              f"log(frequence observee)")

    def test_MAT5_CONTRE_EPREUVE_le_chemin_AVEC_colonnes_est_intact(self):
        """⚠️ Le second sens. Le chemin de production empruntait deja la
        bonne ecriture : la reparation ne doit RIEN y changer. *Un controle
        qui ne verifie qu'un sens accuse.*"""
        d = _jeu(colonnes=2)
        M = _matrice(d, ['x1', 'x2'])
        self.assertEqual(list(M.columns), ['const', 'x1', 'x2'])
        self.assertEqual(M.shape, (len(d), 3))
        self.assertEqual(list(M.index), list(d.index),
                         "la matrice a perdu l'index : la cible et l'offset "
                         "ne s'alignent plus")
        #: les valeurs sont celles des colonnes d'origine, intactes
        for c in ('x1', 'x2'):
            self.assertTrue(
                np.allclose(np.asarray(M[c]), np.asarray(d[c])),
                f"la colonne {c} a ete alteree par la construction")
        res = ajuster_glm_frequence(d, ['x1', 'x2'], 'nb', _offset(d))
        self.assertEqual(sorted(res['modele'].params.index),
                         ['const', 'x1', 'x2'])
        print("    MAT-5 contre-epreuve : le chemin avec colonnes est "
              "inchange, index compris")


if __name__ == '__main__':
    unittest.main(verbosity=2)
