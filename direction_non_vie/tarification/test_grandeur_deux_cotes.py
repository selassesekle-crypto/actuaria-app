"""UNE GRANDEUR A DEUX COTES SE TRAITE DES DEUX COTES -- cause (d).

Le ratio de sur-apprentissage `r = Gini(train) / Gini(test)` a DEUX cotes :
au-dessus de 1 c'est du sur-apprentissage, en dessous c'est une anomalie -- le
Gini de TEST depasse celui d'ENTRAINEMENT. Trois sites le traitaient d'un seul
cote, et chacun DECIDAIT.

  DC-1  la note de stabilite est MAXIMALE en r=1 et decroit des DEUX cotes ;
  DC-2  elle ne depend PLUS du catalogue : meme ratio, meme note, quels que
        soient les autres modeles presents ;
  DC-3  elle est CONTINUE : plus aucune marche de 30 % pour un ecart de
        ratio de 0,0002 ;
  DC-4  `A4-3` -- un Gini d'entrainement nul ou negatif rend `None`, jamais
        un litteral, et le critere SORT du score ;
  DC-5  `A5-1` -- l'hypothese H2 est une BANDE a deux cotes : un Gini de test
        TRIPLE de celui d'entrainement n'est plus VERT ;
  DC-6  et un Gini de test <= 0 reste ROUGE, jamais << non mesurable >> ;
  DC-7  H2 et le classement lisent la MEME grandeur, dans le MEME sens ;
  DC-8  la jauge, seconde surface de la meme grandeur, suit les MEMES bornes.

⚠️⚠️ CE QUE LA MESURE A ETABLI AVANT D'ECRIRE UNE LIGNE (10 LoB x 2 tailles,
chaine complete A1->A6 avec A5, 180 modeles) :
  · **7 runs sur 20** retenaient un modele a `r < 1` note 1,0 ;
  · la part CONTINUE du critere ne separait `r=1` de `r=2` que de 0,08 sur un
    catalogue allant a 13,06, contre 0,61 sur un catalogue allant a 2,60 --
    la note d'un modele dependait d'un AUTRE modele ;
  · toute la discrimination venait de deux MARCHES : `r=1,1499` et `r=1,1501`
    etaient separes de **30 %** de leur note ;
  · le retournement seul du seuil H2 laissait **40/40 statuts identiques** --
    seule la bande a deux cotes ferme le defaut.

⚠️ ET LA CORRECTION D'`A6-2` RENDAIT `A4-3` STRICTEMENT PIRE : sous une
distance a 1, un `r` fabrique a 1,0 devient le score PARFAIT, par
construction. Les deux se corrigent donc ENSEMBLE, jamais l'un sans l'autre.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""

from __future__ import annotations

import math
import unittest
import warnings

import numpy as np

from direction_non_vie.tarification.a5_deep_learning.agent import (
    SEUIL_H2_AMBRE,
    SEUIL_H2_VERT,
)
from direction_non_vie.tarification.a6_comparaison.agent import (
    STABILITE_RATIO_NUL,
    AgentA6Comparaison,
)

_POIDS = {'gini': 0.40, 'stabilite': 0.30, 'interpretabilite': 0.20,
          'rmse': 0.10}


def _modele(nom, ratio, gini=0.20, rmse=0.40, inter=1.0):
    return {'modele': nom, 'famille': 'GLM', 'cible': 'nb_sinistres',
            'gini_test': gini, 'gini_train': None if ratio is None
            else gini * ratio, 'rmse_test': rmse, 'interpretabilite': inter,
            'overfit_ratio': ratio, 'nb_vars': 5}


def _noter(catalogue):
    """Les scores tels que l'agent les calcule, sans lancer la chaine."""
    agent = AgentA6Comparaison.__new__(AgentA6Comparaison)
    return agent._calculer_scores_multicriteres(catalogue, _POIDS)


def _note_de(ratio, autres=()):
    cat = [_modele('CIBLE', ratio)] + [_modele(f'X{i}', r)
                                       for i, r in enumerate(autres)]
    return next(m['score_stabilite'] for m in _noter(cat)
                if m['modele'] == 'CIBLE')


class TestNoteDeStabilite(unittest.TestCase):

    def test_DC1_la_note_est_maximale_en_1_et_decroit_des_DEUX_cotes(self):
        """⚠️⚠️ LE DEFAUT MESURE : la note etait DECROISSANTE en `r`, donc un
        `r = 0,10` -- un Gini de test DIX FOIS celui d'entrainement -- recevait
        la note maximale. 7 runs sur 20 retenaient un tel modele."""
        autres = (0.10, 1.00, 3.00)
        self.assertAlmostEqual(_note_de(1.00, autres), 1.0, places=9,
                               msg='un ratio de 1 doit valoir la note maximale')
        for anomal in (0.10, 0.25, 0.50, 0.80):
            with self.subTest(r=anomal):
                self.assertLess(
                    _note_de(anomal, autres), _note_de(1.00, autres),
                    f'un ratio de {anomal} (Gini de TEST superieur a celui '
                    f"d'ENTRAINEMENT) recoit une note >= a celle d'un ratio "
                    f'parfait : le critere ne regarde qu un cote')
        for surappris in (1.25, 2.00, 4.00):
            with self.subTest(r=surappris):
                self.assertLess(_note_de(surappris, autres),
                                _note_de(1.00, autres))
        print('    DC-1 note maximale en r=1, decroissante des deux cotes')

    def test_DC1b_deux_ratios_INVERSES_recoivent_la_MEME_note(self):
        """⚠️ La symetrie est en RATIO, pas en soustraction : `r = 2` et
        `r = 0,5` sont a la meme distance multiplicative de 1."""
        for r in (1.5, 2.0, 2.5):
            with self.subTest(r=r):
                self.assertAlmostEqual(_note_de(r, (0.2, 1.0, 5.0)),
                                       _note_de(1 / r, (0.2, 1.0, 5.0)),
                                       places=9)
        print('    DC-1b r et 1/r recoivent la meme note')

    def test_DC2_la_note_ne_depend_PLUS_du_catalogue(self):
        """⚠️⚠️ LE SECOND DEFAUT, MESURE. `1 - (r-min)/(max-min)` faisait
        dependre la note d'un modele de la presence d'un AUTRE modele
        aberrant : l'ecart entre r=1 et r=2 valait 0,08 sur un catalogue
        allant a 13,06 et 0,61 sur un catalogue allant a 2,60."""
        maigre = _note_de(1.30, (1.00, 1.60))
        large = _note_de(1.30, (1.00, 18.98))
        self.assertAlmostEqual(
            maigre, large, places=9,
            msg=f'la note du MEME ratio change avec le catalogue : '
                f'{maigre} contre {large}')
        print(f'    DC-2 r=1,30 note {maigre:.4f} quel que soit le catalogue')

    def test_DC3_la_note_est_CONTINUE_plus_aucune_marche(self):
        """⚠️⚠️ Deux modeles a `r = 1,1499` et `r = 1,1501` etaient separes de
        30 % de leur note, quand `r = 1,5` et `r = 3,0` ne l'etaient que de
        11 %. *Discontinu la ou il fallait etre lisse, lisse la ou il fallait
        trancher.*"""
        autres = (0.9, 1.0, 3.0)
        for gauche, droite in ((1.1499, 1.1501), (1.2999, 1.3001)):
            with self.subTest(seuil=gauche):
                saut = abs(_note_de(gauche, autres) - _note_de(droite, autres))
                self.assertLess(
                    saut, 0.01,
                    f'chute de {saut:.4f} pour un ecart de ratio de '
                    f'{droite - gauche:.4f} : une MARCHE decide encore')
        # et le critere doit trancher LA ou l ecart est reel
        ecart_reel = abs(_note_de(1.5, autres) - _note_de(3.0, autres))
        self.assertGreater(
            ecart_reel, 0.10,
            f'r=1,5 et r=3,0 ne sont separes que de {ecart_reel:.4f} : le '
            f'critere ne tranche pas la ou il devrait')
        print(f'    DC-3 saut aux anciens seuils < 0,01 · ecart 1,5 vs 3,0 = '
              f'{ecart_reel:.4f}')

    def test_DC3b_le_seuil_de_note_nulle_est_NOMME(self):
        """Un `3` recopie a la main diverge ; une constante ne le peut pas."""
        self.assertAlmostEqual(STABILITE_RATIO_NUL, math.log(3), places=12)
        self.assertAlmostEqual(_note_de(3.0, (1.0,)), 0.0, places=9)
        self.assertAlmostEqual(_note_de(1 / 3, (1.0,)), 0.0, places=9)
        print('    DC-3b note nulle a r=3 et r=1/3, seuil nomme')


class TestRatioNonMesure(unittest.TestCase):

    def test_DC4_un_ratio_absent_fait_SORTIR_le_critere_du_score(self):
        """⚠️⚠️ SANS CELA, LA CORRECTION D'`A6-2` AURAIT AGGRAVE `A4-3` : sous
        une distance a 1, un `r` fabrique a 1,0 est le score PARFAIT."""
        cat = _noter([_modele('SANS', None), _modele('AVEC', 1.20)])
        sans = next(m for m in cat if m['modele'] == 'SANS')
        self.assertIsNone(sans['score_stabilite'])
        self.assertIn('stabilite', sans['criteres_non_mesures'])
        print('    DC-4 ratio absent : critere hors du score, declare')

    def test_DC4b_A4_rend_None_sur_un_Gini_d_entrainement_NUL(self):
        """⚠️ Le litteral `1.0` valait, sous la nouvelle formule, la note
        PARFAITE garantie pour un modele qui n'a rien appris sur le train."""
        warnings.filterwarnings('ignore')
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML

        agent = AgentA4ML.__new__(AgentA4ML)
        rng = np.random.default_rng(4)
        n = 400
        y_train = rng.poisson(0.3, n).astype(float)
        y_test = rng.poisson(0.3, n).astype(float)
        poids = np.ones(n)
        metriques = agent._calculer_metriques(
            y_train=y_train, y_test=y_test,
            # ⚠️ PREDICTION CONSTANTE sur le train : tous les contrats sont
            # ex aequo, le Gini d'entrainement vaut 0. C'est le declencheur
            # exact de la branche `gini_train <= 0`.
            pred_train=np.full(n, 0.3),
            pred_test=y_test * 0.9 + 0.05,
            w_train=poids, w_test=poids, nom='sonde')
        self.assertIsNotNone(metriques.get('gini_train'))
        self.assertLessEqual(metriques['gini_train'], 0)
        self.assertIsNone(
            metriques['overfit_ratio'],
            "un Gini d'entrainement nul publie encore un ratio fabrique : "
            f"{metriques['overfit_ratio']}")
        print(f'    DC-4b gini_train={metriques["gini_train"]} '
              f'-> overfit_ratio=None')


class TestHypotheseH2(unittest.TestCase):
    """⚠️ On exerce la REGLE, pas le reseau : H2 ne depend que du couple
    (gini_train, gini_test) du modele DL de tete."""

    @staticmethod
    def _h2(gini_train, gini_test):
        """⚠️⚠️ ON APPELLE LA VRAIE FONCTION, PAS UNE REPLIQUE. Une premiere
        version de ce controle reimplementait la regle dans le test : elle
        serait restee VERTE le jour ou l'agent aurait diverge d'elle. *Un
        controle qui teste sa propre copie ne surveille rien.*
        """
        from direction_non_vie.tarification.a5_deep_learning.agent import (
            AgentA5DeepLearning,
        )
        agent = AgentA5DeepLearning.__new__(AgentA5DeepLearning)
        metriques = {'cann': {'gini_test': gini_test,
                              'gini_train': gini_train}}
        val = agent._valider_hypotheses_dl(
            classement=[{'modele': 'cann', 'gini_test': gini_test}],
            metriques=metriques, n_epochs=10)
        return val['h2_surapprentissage']

    @classmethod
    def _statut(cls, gini_train, gini_test):
        return cls._h2(gini_train, gini_test)['statut']

    def test_DC5_un_Gini_de_test_TRIPLE_n_est_plus_VERT(self):
        """⚠️⚠️ LE DEFAUT QUE LE RETOURNEMENT SEUL NE FERMAIT PAS. Mesure :
        inverser le seuil laissait 40/40 statuts identiques ; un
        `gini_test = 3 x gini_train` sortait VERT avant comme apres."""
        self.assertEqual(self._statut(0.10, 0.30), 'ROUGE')
        self.assertEqual(self._statut(0.20, 0.60), 'ROUGE')
        print('    DC-5 Gini de test triple : ROUGE, plus VERT')

    def test_DC5b_la_bande_est_symetrique_en_ratio(self):
        for gt, gte in ((0.20, 0.20), (0.22, 0.20), (0.20, 0.22)):
            with self.subTest(train=gt, test=gte):
                self.assertEqual(self._statut(gt, gte), 'VERT')
        # les deux cotes sortent du VERT au meme ecart multiplicatif
        self.assertEqual(self._statut(0.20 / SEUIL_H2_VERT * 1.02, 0.20),
                         'AMBRE')
        self.assertEqual(self._statut(0.20, 0.20 / SEUIL_H2_VERT * 1.02),
                         'AMBRE')
        # ⚠️ ET LA BANDE AMBRE EST SYMETRIQUE ELLE AUSSI : ses deux bornes
        # sont `SEUIL_H2_AMBRE` et son INVERSE, jamais une seule.
        self.assertEqual(self._statut(0.20 / SEUIL_H2_AMBRE * 1.02, 0.20),
                         'ROUGE')
        self.assertEqual(self._statut(0.20, 0.20 / SEUIL_H2_AMBRE * 1.02),
                         'ROUGE')
        print('    DC-5b bandes VERT et AMBRE symetriques en ratio')

    def test_DC6_un_Gini_de_test_NEGATIF_reste_ROUGE(self):
        """⚠️⚠️ ARBITRE PAR SELASSE. Le socle rendrait `None` ; ce serait une
        regression : un Gini de test <= 0 dit que le modele ne discrimine pas
        sur son jeu d'evaluation. C'est une ALERTE, pas une absence."""
        for gte in (-0.02, -0.20, 0.0):
            with self.subTest(gini_test=gte):
                self.assertEqual(
                    self._statut(0.20, gte), 'ROUGE',
                    'un Gini de test negatif ou nul disparait dans une case '
                    '<< non mesurable >> au lieu d alerter')
        print('    DC-6 Gini de test <= 0 : ROUGE conserve')

    def test_DC7_H2_et_le_classement_lisent_la_MEME_grandeur(self):
        """⚠️⚠️ `A5-1` : le meme fichier calculait la meme grandeur dans les
        DEUX SENS -- 1,111 au classement et 0,900 chez H2, deux nombres
        reciproques sous le meme libelle, sur la meme page."""
        import inspect

        from core.conformite_reglementaire import ratio_sur_apprentissage
        from direction_non_vie.tarification.a5_deep_learning import (
            agent as A5,
        )
        src = inspect.getsource(A5._valider_hypotheses_dl) \
            if hasattr(A5, '_valider_hypotheses_dl') else inspect.getsource(
                A5.AgentA5DeepLearning._valider_hypotheses_dl)
        self.assertNotIn(
            'max(gini_train, 0.001)', src,
            'H2 recalcule le ratio a la main au lieu de lire la source unique')
        self.assertIn('ratio_sur_apprentissage', src)
        # et la grandeur elle-meme, verifiee par la valeur
        self.assertAlmostEqual(ratio_sur_apprentissage(0.20, 0.18),
                               0.20 / 0.18, places=9)
        print('    DC-7 H2 passe par la source unique, meme sens')

    def test_DC8_la_JAUGE_suit_les_memes_bornes(self):
        """⚠️⚠️ SURFACE JUMELLE. La jauge codait ses bandes en dur -- elle
        disait << [0,88 ; 1,5] = vert >> sur `test/train` ; sur `train/test`
        un ratio de 1,40, du vrai sur-apprentissage, s y serait affiche en
        VERT. *Le correctif qui n'atteint pas la surface jumelle transforme
        une correction en defaut.*"""
        import inspect

        from direction_non_vie.tarification.a5_deep_learning import (
            agent as A5,
        )
        src = inspect.getsource(A5.AgentA5DeepLearning)
        debut = src.find('jauge_surapprentissage')
        bloc = src[max(0, debut - 4000):debut]
        self.assertIn('SEUIL_H2_VERT', bloc,
                      'la jauge ne lit pas la borne nommee : ses seuils '
                      'peuvent diverger de ceux du statut')
        self.assertNotIn('range=[0, 1.5]', bloc,
                         'la jauge garde son axe unilateral')
        print('    DC-8 la jauge lit les bornes nommees')


if __name__ == '__main__':
    unittest.main(verbosity=2)
