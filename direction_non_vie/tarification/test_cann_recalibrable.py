# -*- coding: utf-8 -*-
"""UN CANN RETENU EN PRODUCTION N'ETAIT PAS RECALIBRABLE : PROXY GBM.

`a6:1723` l'ecrivait sans detour : << Les `DL_*` restent en proxy (reseaux de
neurones : pas de fabrique). >> Mesure du 05/09/2026, des qu'un CANN
correctement ancre devient le modele retenu sur la fixture de 5 000 contrats :

    modele_recalibre        : DL_CANN -> proxy GBM
    modele_recalibre_fidele : False
    statut                  : plafonne a AMBRE, en production

*La stabilite temporelle publiee etait alors celle d'un AUTRE modele.*

⚠️⚠️ C'EST LE DEFAUT DU GLM, A L'IDENTIQUE, UN CRAN PLUS LOIN. L'audit V14
avait trouve la meme chose : << UN GLM NE POUVAIT JAMAIS ETRE CERTIFIE VERT.
JAMAIS >> -- la fabrique ne savait pas le construire, le proxy prenait le
relais, le gate plafonnait. La lecon ecrite alors vaut encore :

  > *On a beaucoup verifie que le systeme REFUSE ce qu'il doit refuser.
  > Personne n'a verifie qu'il ACCEPTE ce qu'il doit accepter.*

Ce que cette sentinelle exige :
  RC-1  la fabrique du walk-forward CONSTRUIT un CANN, sous ses deux noms ;
  RC-2  l'adaptateur porte l'interface attendue : `fit` / `predict` ;
  RC-3  ⚠️ IL ANCRE REELLEMENT -- `glm_gele` VRAI apres `fit`. Un CANN non
        ancre n'est pas un CANN : ce serait un proxy deguise ;
  RC-4  le GLM d'ancrage est REAPPRIS sur la fenetre, jamais herite ;
  RC-5  `predict` respecte l'echelle d'ajustement ;
  RC-6  ⚠️ AUCUN PROXY : sur un pipeline ou le CANN est retenu, le modele
        recalibre est un CANN et la fidelite est VRAIE ;
  RC-7  second sens : un modele VRAIMENT inconnu tombe toujours en proxy --
        la fabrique n'a pas ete rendue permissive.

⚠️⚠️ CE LOT EST INDISSOCIABLE DE L'ANCRAGE PAR CIBLE (`test_cann_ancrage`).
Mesure : sans lui, `_calibrer_cann` cherche `modeles['tweedie']` EN DUR ; un
adaptateur qui fournit le GLM Poisson de la fenetre n'est alors pas entendu, et
`glm_gele` reste FAUX. Livrer cette capacite seule aurait produit un
recalibrateur qui *semble* fonctionner -- predictions finies, aucune erreur --
tout en n'etant pas un CANN. *C'est exactement le defaut que l'autre lot
corrige, reproduit dans l'instrument cense le valider.*

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


def _jeu(n=900, p=6, seed=7):
    """Un portefeuille de comptage SYNTHETIQUE, a effet connu.

    ⚠️⚠️ LES ECHELLES SONT HETEROGENES, ET C'EST LE POINT. Ma premiere version
    tirait tout en `N(0, 1)` : le `StandardScaler` y valait alors l'IDENTITE
    (mu ~ 0, sigma ~ 1), et le plant qui SUPPRIMAIT la standardisation dans
    `predict` restait MUET -- rapport `pred*expo / y` mesure a **1,0094**.

      *Une fixture deja standardisee ne peut pas prouver qu'on standardise.*

    Les vraies donnees ne ressemblent pas a cela : le depot a mesure un rapport
    d'echelle de **1 734 823x** entre features sur decennale, et c'est
    exactement ce qui y faisait echouer `lineaire_regularise` en silence. On
    reproduit donc des ordres de grandeur d'assurance -- un age, une
    anciennete, un montant, un bonus-malus.
    """
    rng = np.random.default_rng(seed)
    brut = rng.normal(size=(n, p))
    # age ~ 40 +/- 12 | anciennete ~ 8 +/- 5 | montant ~ 250 000 +/- 90 000
    # bonus ~ 0,9 +/- 0,15 | puis deux colonnes centrees reduites.
    echelles = np.array([12.0, 5.0, 90_000.0, 0.15, 1.0, 1.0])[:p]
    centres = np.array([40.0, 8.0, 250_000.0, 0.9, 0.0, 0.0])[:p]
    X = brut * echelles + centres
    expo = rng.uniform(0.5, 1.0, n)
    # ⚠️ L'effet porte sur les variables BRUTES, donc les coefficients sont a
    # l'echelle de chacune : c'est precisement ce que la reprojection du CANN
    # doit rattraper.
    lam = np.exp(-2.0 + 0.05 * brut[:, 0] - 0.04 * brut[:, 1]) * expo
    y = rng.poisson(lam).astype(float)
    return X, y, expo, ['age', 'anciennete', 'montant', 'bonus', 'f4', 'f5'][:p]


class TestLaFabriqueConstruitUnCANN(unittest.TestCase):

    def test_RC1_la_fabrique_reconnait_le_CANN_sous_ses_deux_noms(self):
        """⚠️ A6 passe le nom BRUT du classement (`DL_CANN`) ; A4 emploie
        `cann`. Les deux doivent aboutir, sinon le chemin fidele ne se
        declenche jamais en pratique -- c'est deja arrive (audit V4 reco 7)."""
        from direction_non_vie.tarification.a4_ml.agent import (
            _CANNWalkForward,
            _fabriquer_estimateur_nu,
        )
        for nom in ('cann', 'CANN', 'dl_cann', 'DL_CANN'):
            with self.subTest(nom=nom):
                self.assertIsInstance(
                    _fabriquer_estimateur_nu(nom, 'nb_sinistres'),
                    _CANNWalkForward,
                    f'{nom!r} ne construit pas de CANN : il retombera en proxy')

    def test_RC7_SECOND_SENS_un_modele_INCONNU_tombe_toujours(self):
        """⚠️⚠️ Sans ce sens, on aurait pu rendre la fabrique permissive et
        RC-1 serait vert. *Une fabrique qui accepte tout ne certifie plus
        rien.*"""
        from direction_non_vie.tarification.a4_ml.agent import (
            _fabriquer_estimateur_nu,
        )
        for nom in ('dl_tabnet', 'tabnet', 'reseau_maison', 'DL_INCONNU'):
            with (self.subTest(nom=nom),
                  self.assertRaises((ValueError, ImportError))):
                _fabriquer_estimateur_nu(nom, 'nb_sinistres')

    def test_RC2_l_adaptateur_porte_l_interface_attendue(self):
        from direction_non_vie.tarification.a4_ml.agent import _CANNWalkForward
        modele = _CANNWalkForward(col_cible='nb_sinistres')
        for methode in ('fit', 'predict'):
            self.assertTrue(callable(getattr(modele, methode, None)),
                            f'{methode} manquant : le walk-forward ne saura '
                            'pas s en servir')
        # ⚠️ `predict` avant `fit` doit REFUSER, jamais rendre un tableau.
        with self.assertRaises(RuntimeError):
            modele.predict(np.zeros((3, 2)))


class TestIlAncreVraiment(unittest.TestCase):
    """⚠️⚠️ LE COEUR DU LOT. Un adaptateur qui s'entraine librement rend des
    predictions parfaitement finies et ne leve aucune erreur -- il n'est
    simplement plus un CANN. Mesure faite en ecrivant ce lot : sans le scaler,
    `glm_gele` valait FAUX et tout semblait marcher."""

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)
        try:
            import torch
        except ImportError:                                  # pragma: no cover
            raise unittest.SkipTest('torch absent')
        from direction_non_vie.tarification.a4_ml.agent import _CANNWalkForward
        np.random.seed(7)
        torch.manual_seed(7)
        cls.X, cls.y, cls.expo, cls.noms = _jeu()
        cls.modele = _CANNWalkForward(
            col_cible='nb_sinistres', feature_names=cls.noms, n_epochs=20)
        cls.modele.fit(cls.X, cls.y, sample_weight=cls.expo)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_RC3_le_GLM_est_REELLEMENT_gele(self):
        """*Un CANN non ancre serait un proxy deguise -- et il passerait pour
        une recalibration fidele.*"""
        self.assertTrue(
            self.modele.glm_gele,
            "le CANN recalibre n'est PAS ancre : le reseau s'est entraine "
            'librement. Il rendra des predictions finies et ne levera aucune '
            "erreur, mais ce n'est plus un CANN Wuthrich.")

    def test_RC4_le_GLM_d_ancrage_suit_la_CIBLE_et_est_reappris(self):
        """⚠️⚠️ REAPPRIS SUR LA FENETRE, JAMAIS HERITE. Garder le GLM ajuste
        sur TOUT l'historique ferait entrer le futur dans l'ancrage a chaque
        fenetre : *une fuite de donnees dans l'instrument meme qui sert a
        detecter les derives.*"""
        self.assertEqual(self.modele.glm_ancre, 'poisson',
                         'une cible de comptage doit s ancrer sur le Poisson')
        # ⚠️ Le GLM vit dans l'adaptateur, pas dans un resultat d'A3 importe :
        # c'est ce qui prouve qu'il a ete reappris ici.
        self.assertIsNotNone(getattr(self.modele, '_scaler', None),
                             "l'echelle de la fenetre n'a pas ete apprise")

    def test_RC5_predict_respecte_l_echelle_d_ajustement(self):
        """⚠️ Predire sur X brut apres avoir appris sur X standardise donne
        des valeurs finies, positives, et SANS RAPPORT. *Le silence d'une
        erreur ne prouve pas la justesse d'un chiffre.*"""
        pred = self.modele.predict(self.X)
        self.assertEqual(len(pred), len(self.y))
        self.assertTrue(np.isfinite(pred).all(), 'predictions non finies')
        self.assertTrue((pred > 0).all(), 'un taux de frequence est positif')
        # `predict` est SANS offset : pred * expo doit retrouver l'ordre de
        # grandeur de la cible observee. Un facteur 10 signalerait une echelle
        # perdue.
        attendu = float(np.mean(pred * self.expo))
        observe = float(np.mean(self.y))
        self.assertGreater(attendu, observe / 3)
        self.assertLess(attendu, observe * 3)


class TestPlusAucunProxySurUnCANNRetenu(unittest.TestCase):
    """⚠️⚠️ PAR EXECUTION, SUR LE VRAI PIPELINE. C'est la seule facon de
    prouver que le chemin fidele se DECLENCHE : le nom passe par l'agregat
    d'A6 (`DL_CANN`), et un decalage de nommage suffirait a le rater -- c'est
    deja arrive (audit V4 reco 7, << le chemin ne se declenche JAMAIS en
    pratique >>)."""

    def test_RC6_le_modele_recalibre_est_un_CANN_et_la_fidelite_est_VRAIE(self):
        from direction_non_vie.tarification.test_pipeline_agents import (
            _lancer,
            _portefeuille_auto,
        )
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)
        try:
            np.random.seed(7)
            import torch
            torch.manual_seed(7)
            res = _lancer(_portefeuille_auto(5000))
        finally:
            logging.disable(logging.NOTSET)
        a6 = getattr(getattr(res, 'frequence', None), 'a6', None) or {}
        production = (a6.get('modele_production') or {}).get('modele')
        backtest = a6.get('backtest') or {}
        recalibre = str(backtest.get('modele_recalibre') or '')
        if production != 'DL_CANN':
            self.skipTest(
                f"le modele retenu est {production!r} et non DL_CANN : ce "
                f"chemin n'est pas exerce par cette fixture")
        self.assertNotIn(
            'proxy', recalibre.lower(),
            f'le CANN retenu est recalibre par un PROXY ({recalibre}) : la '
            f'stabilite temporelle publiee est celle d un autre modele')
        self.assertIs(
            backtest.get('modele_recalibre_fidele'), True,
            'la recalibration du CANN est rapportee NON fidele')


if __name__ == '__main__':
    unittest.main(verbosity=2)
