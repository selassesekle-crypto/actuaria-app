"""L'ARRET ANTICIPE NE SE REGLE PAS SUR LE PLI QU'IL MESURE -- constat `A4-4`.

`_CANNWalkForward.fit` passait la MEME tranche en validation et en test :
l'arret anticipe choisissait donc son modele sur les lignes qui servent
ensuite a le noter. Et la garde de `_calibrer_cann` promettait le contraire
dans son propre message -- << un jeu de VALIDATION distinct, jamais le
test >> -- en ne verifiant que la PRESENCE.

  AA-1  la validation passee par le walk-forward est DISJOINTE du test ;
  AA-2  et la garde REFUSE un jeu de validation qui recouvre le test --
        c'est une propriete qu'elle verifie, plus une presence ;
  AA-3  mais elle TOLERE un recouvrement marginal : deux contrats aux memes
        facteurs existent dans un vrai portefeuille (controle NEGATIF) ;
  AA-4  le seuil de recouvrement est NOMME, jamais recopie ;
  AA-5  une fenetre trop courte pour porter une validation REFUSE, au lieu
        de se replier en silence sur le test.

⚠️⚠️ CE QUE LA MESURE A ETABLI, ET QUI CORRIGE L'AUDIT. Celui-ci ecrit
<< Je n'ai PAS mesure de combien >> le Gini en est gonfle. Mesure du
07/09/2026, huit graines, MEME entrainement et MEMES graines des deux cotes
-- seule la validation differe, donc seule l'EPOQUE RETENUE peut changer :

    6 / 8 graines ou la fuite change l'epoque retenue
    ecart de Gini de test : min -0,0039 · max +0,0030 · MOYEN +0,0001

Le mecanisme est donc bien vivant -- la validation selectionne un autre
modele trois fois sur quatre -- mais le Gini publie bouge d'au plus 0,004,
SANS DIRECTION SYSTEMATIQUE. *Le CANN est domine par son GLM gele : l'epoque
d'arret ne change presque rien a sa performance.* Le correctif ne se justifie
donc pas par son amplitude, il se justifie parce qu'un arret anticipe regle
sur le pli d'evaluation est indefendable dans un document signe.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""

from __future__ import annotations

import unittest
import warnings

import numpy as np

from direction_non_vie.tarification.a5_deep_learning.agent import (
    SEUIL_RECOUVREMENT_VALIDATION,
)


def _jeu(n=400, p=4, graine=11):
    rng = np.random.default_rng(graine)
    X = rng.normal(size=(n, p))
    expo = rng.uniform(0.4, 1.0, n)
    y = rng.poisson(expo * np.exp(-1.6 + 0.5 * X[:, 0] - 0.3 * X[:, 1]))
    return X, y.astype(float), expo


class _Arret(Exception):
    """Interrompt la calibration des que l'espion a releve ce qu'il faut."""


class TestValidationDisjointeDuTest(unittest.TestCase):

    def test_AA1_le_walk_forward_passe_une_validation_DISJOINTE(self):
        """⚠️⚠️ MESURE, PAS LECTURE. On espionne l'appel reel et on compare les
        LIGNES : `X_val` et `X_test` n'etaient pas le meme OBJET -- deux
        tranches distinctes -- mais portaient les memes valeurs. Un controle
        par `is` n'aurait rien vu, et c'est exactement ce qui a laisse le
        defaut vivre."""
        warnings.filterwarnings('ignore')
        import direction_non_vie.tarification.a5_deep_learning.agent as A5M
        from direction_non_vie.tarification.a4_ml.agent import (
            _CANNWalkForward,
        )

        vu: dict = {}
        origine = A5M.AgentA5DeepLearning._calibrer_cann

        def espion(self, **kw):
            vu.update(kw)
            raise _Arret()

        X, y, expo = _jeu()
        A5M.AgentA5DeepLearning._calibrer_cann = espion
        try:
            _CANNWalkForward(col_cible='nb_sinistres', n_epochs=2,
                             batch_size=64).fit(X, y, sample_weight=expo)
        except _Arret:
            pass
        finally:
            A5M.AgentA5DeepLearning._calibrer_cann = origine

        self.assertTrue(vu, "l'espion n'a rien releve : la mesure est vide")
        val, test = np.asarray(vu['X_val']), np.asarray(vu['X_test'])
        train = np.asarray(vu['X_train'])
        self.assertTrue(len(val) and len(test) and len(train))

        def lignes(tab):
            return {tuple(np.round(np.asarray(x, dtype=float), 12))
                    for x in tab}

        communes = len(lignes(val) & lignes(test))
        self.assertEqual(
            communes, 0,
            f"{communes} ligne(s) de la validation se retrouvent dans le "
            f"test : l'arret anticipe se regle sur le pli qui mesure")
        self.assertFalse(
            np.array_equal(val, test),
            'la validation EST le test (memes valeurs)')
        print(f'    AA-1 walk-forward : train {len(train)} · val {len(val)} · '
              f'test {len(test)}, 0 ligne commune')

    def test_AA5_une_fenetre_trop_courte_REFUSE_au_lieu_de_se_replier(self):
        """⚠️ Un repli silencieux sur le test rouvrirait le constat. On refuse,
        et le message dit pourquoi."""
        warnings.filterwarnings('ignore')
        from direction_non_vie.tarification.a4_ml.agent import (
            _CANNWalkForward,
        )
        # ⚠️ 60 lignes donnent coupe=51 et coupe_fit=43, soit 8 lignes de
        # validation -- sous le minimum. Et la GARDE PASSE AVANT LE GLM :
        # placee apres, elle etait inatteignable (statsmodels mourait le
        # premier, sur une deviance NaN).
        X, y, expo = _jeu(n=60)
        with self.assertRaises(ValueError) as cm:
            _CANNWalkForward(col_cible='nb_sinistres', n_epochs=1).fit(
                X, y, sample_weight=expo)
        message = str(cm.exception)
        self.assertIn('VALIDATION', message.upper())
        self.assertIn(str(_CANNWalkForward.MIN_VALIDATION), message)
        print('    AA-5 fenetre trop courte : refus explicite, avant le GLM')


class TestGardeDePropriete(unittest.TestCase):
    """⚠️ La garde exercee DIRECTEMENT : elle promettait la distinction dans
    son message et ne verifiait que la presence."""

    @staticmethod
    def _appeler(X_val, X_test):
        import torch

        from direction_non_vie.tarification.a5_deep_learning.agent import (
            AgentA5DeepLearning,
        )
        agent = AgentA5DeepLearning.__new__(AgentA5DeepLearning)
        agent.scalers = {}
        agent._cible_run = 'nb_sinistres'
        n_v, n_t = len(X_val), len(X_test)
        return agent._calibrer_cann(
            X_train=np.zeros((10, X_test.shape[1]), dtype=np.float32),
            X_test=X_test.astype(np.float32),
            y_train=np.zeros(10, dtype=np.float32),
            y_test=np.zeros(n_t, dtype=np.float32),
            feature_names=[f'x{i}' for i in range(X_test.shape[1])],
            device=torch.device('cpu'), n_epochs=1, batch_size=8, lr=1e-3,
            result_a3=None,
            expo_train=np.ones(10), expo_test=np.ones(n_t),
            X_val=X_val.astype(np.float32),
            y_val=np.zeros(n_v, dtype=np.float32), expo_val=np.ones(n_v))

    def test_AA2_la_garde_REFUSE_une_validation_qui_est_le_test(self):
        """⚠️⚠️ DEUX OBJETS DISTINCTS, MEME CONTENU -- c'est la forme REELLE du
        defaut. `_CANNWalkForward` passait deux TRANCHES differentes du meme
        tableau : `X_val is X_test` rendait False alors que les 60 lignes
        etaient partagees. *Une garde qui comparerait par identite serait
        muette ici, et c'est precisement ce que le sceau plante.*"""
        X, _, _ = _jeu(n=60)
        copie = X.copy()
        self.assertIsNot(copie, X)
        with self.assertRaises(ValueError) as cm:
            self._appeler(copie, X)
        message = str(cm.exception)
        self.assertIn('VALIDATION', message.upper())
        self.assertIn('60/60', message)
        print('    AA-2 validation = test : refus, avec le compte')

    def test_AA3_elle_TOLERE_un_recouvrement_marginal(self):
        """⚠️ CONTROLE NEGATIF DECLARE. Refuser sur UNE ligne commune ferait
        tomber des decoupages legitimes : deux contrats aux memes facteurs
        existent. Ce qui trahit une validation qui EST le test, c'est le
        recouvrement MASSIF.

        On n'attend pas que la calibration REUSSISSE ici (elle a d'autres
        exigences) : on exige seulement qu'elle ne tombe PAS sur le
        recouvrement.
        """
        X, _, _ = _jeu(n=60)
        val = np.vstack([X[:5], _jeu(n=55, graine=99)[0]])   # 5/60 communes
        try:
            self._appeler(val, X)
        except Exception as erreur:                            # noqa: BLE001
            # ⚠️ UNE AUTRE PANNE NE NOUS CONCERNE PAS ICI : on exige seulement
            # que la garde de RECOUVREMENT ne soit pas celle qui tombe.
            self.assertNotIn(
                'partage', str(erreur),
                'un recouvrement de 5 lignes sur 60 fait tomber la garde : '
                'elle refuse des decoupages legitimes')
        print('    AA-3 recouvrement de 5/60 : la garde ne tombe pas')

    def test_AA6_TABNET_porte_la_MEME_garde(self):
        """⚠️⚠️ LA SURFACE JUMELLE. `_calibrer_tabnet` exigeait aussi un
        `X_val` non nul et promettait aussi << distinct, jamais sur le test >>
        sans le verifier. Aucun appelant ne la viole aujourd'hui -- mais
        corriger le CANN seul aurait laisse ici une promesse creuse, et c'est
        le motif que ce chantier a paye deux fois.

        ⚠️⚠️ ON APPELLE `_calibrer_tabnet`, PAS LA GARDE. Une premiere version
        de ce controle invoquait la fonction factorisee directement : le sceau
        l'a prise en defaut -- retirer l'appel DANS TabNet ne la faisait pas
        rougir. *Je verifiais le mecanisme, pas le SITE.*
        """
        import torch

        from direction_non_vie.tarification.a5_deep_learning.agent import (
            AgentA5DeepLearning,
        )
        X, _, _ = _jeu(n=40)
        agent = AgentA5DeepLearning.__new__(AgentA5DeepLearning)
        with self.assertRaises(ValueError) as cm:
            agent._calibrer_tabnet(
                np.zeros((10, X.shape[1]), dtype=np.float32),
                X.astype(np.float32),
                np.zeros(10, dtype=np.float32),
                np.zeros(len(X), dtype=np.float32),
                [f'x{i}' for i in range(X.shape[1])],
                torch.device('cpu'), 1, 8, 1e-3,
                X_val=X.copy().astype(np.float32),
                y_val=np.zeros(len(X), dtype=np.float32))
        self.assertIn('_calibrer_tabnet', str(cm.exception))
        self.assertIn('VALIDATION', str(cm.exception).upper())
        print('    AA-6 TabNet APPELLE la garde partagee')

    def test_AA4_le_seuil_de_recouvrement_est_NOMME(self):
        self.assertGreater(SEUIL_RECOUVREMENT_VALIDATION, 0.0)
        self.assertLess(SEUIL_RECOUVREMENT_VALIDATION, 1.0)
        print(f'    AA-4 seuil nomme : {SEUIL_RECOUVREMENT_VALIDATION}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
