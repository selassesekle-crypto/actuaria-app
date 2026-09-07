"""UNE ABSENCE D'A/E N'EST PAS UN BIAIS -- constat `MES-1`, et la branche morte.

`avertissement_walk_forward` publiait dans les SIX surfaces signees :

    ⚠ BIAIS DE TARIFICATION -- A/E walk-forward = None, hors de la bande
    acceptable [0,90 ; 1,10]. Le modele sur- ou sous-tarifie systematiquement.

Le litteral `None` en toutes lettres, et surtout **une CAUSE affirmee** : une
conclusion sur le modele de l'actuaire, tiree d'une mesure qui n'a pas eu lieu.

⚠️⚠️ ET LE CORRECTIF DU 06/09 ETAIT DU CODE MORT. Une quatrieme branche avait
ete ajoutee TOUT EN BAS de la fonction, sur `cv is None`. Elle ne pouvait
jamais se declencher : `ae_cv_wf` ne vaut `None` que quand la liste des A/E
est vide (`a6:2084`), et dans cet etat `ae_ratio` -- l'A/E de la DERNIERE
fenetre -- vaut `None` lui aussi, donc le test de bande rendait plus haut.
*Un correctif place APRES la branche qui court-circuite est du code mort.*

⛔⛔ ET MON PROPRE SCEAU L'A MANQUE. Le test de `TR-1` appelait la fonction
avec un `backtest` ASSEMBLE A LA MAIN (`ae_ratio: 1.00`, `ae_cv_wf: None`) --
un etat qu'A6 ne peut pas produire. Il prouvait le MECANISME, jamais son
ATTEIGNABILITE. C'est pourquoi `MW-2` ci-dessous derive les champs comme A6
les derive, au lieu de les poser.

  MW-1  aucune fenetre sans A/E ne recoit plus de verdict de biais ;
  MW-2  et le cas est ATTEIGNABLE par l'arithmetique reelle d'A6 ;
  MW-3  second sens : un A/E MESURE a 0,0 reste un biais ;
  MW-4  une derniere fenetre sans A/E se distingue d'aucune fenetre du tout ;
  MW-5  tout message qui nomme une CAUSE est vrai dans l'etat qui l'atteint ;
  MW-6  second sens : un walk-forward sain reste muet ;
  MW-7  le couplage dont depend le discriminant est pinne, par AST.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""

from __future__ import annotations

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

from core.conformite_reglementaire import (
    avertissement_walk_forward,
)

_A6 = pathlib.Path(_ICI) / 'a6_comparaison' / 'agent.py'

#: Les deux gardes amont. Sans elles la fonction sort avant tout ce qui nous
#: interesse -- une premiere version d'une sonde voisine a mesure NEUF cas
#: pour rien faute de les poser.
_AMONT = {'disponible': True, 'modele_recalibre_fidele': True,
          'gini_wf_moyen': 0.20, 'n_fenetres_rouge': 0}


def _backtest_depuis_fenetres(fenetres):
    """Derive le `backtest` comme `a6._backtesting_temporel` le derive.

    ⚠️⚠️ C'EST TOUT L'ENJEU DE CE FICHIER. Poser `ae_ratio` et `ae_cv_wf` a la
    main permet de fabriquer des etats qu'A6 ne produit jamais -- et c'est
    exactement ce que faisait le controle que ce lot repare. Ici on part des
    FENETRES, et les trois champs se deduisent, comme en production.
    """
    derniere = fenetres[-1]
    ae_ratio = derniere['ae_ratio']
    aes = [w['ae_ratio'] for w in fenetres if w['ae_ratio'] is not None]
    ae_moyen = float(np.mean(aes)) if aes else None
    ae_cv = (float(np.std(aes) / max(ae_moyen, 1e-6))
             if aes and ae_moyen else None)
    return dict(_AMONT, ae_ratio=ae_ratio, ae_moyen_wf=ae_moyen,
                ae_cv_wf=ae_cv, n_fenetres=len(fenetres))


class TestAbsenceNEstPasUnVerdict(unittest.TestCase):

    def test_MW1_aucune_fenetre_sans_AE_ne_recoit_plus_de_verdict(self):
        """⚠️⚠️ LE CONSTAT `MES-1`. Une absence recevait « hors de la bande
        acceptable » et « sur- ou sous-tarifie systematiquement »."""
        bt = _backtest_depuis_fenetres(
            [{'ae_ratio': None}, {'ae_ratio': None}, {'ae_ratio': None}])
        msg = avertissement_walk_forward(bt) or ''
        self.assertNotIn(
            'BIAIS DE TARIFICATION', msg,
            'une absence d A/E est encore publiee comme un biais de '
            'tarification dans les six surfaces signees')
        self.assertNotIn('sous-tarifie', msg)
        self.assertNotIn(
            'None', msg,
            'le litteral `None` figure encore dans un livrable signe')
        self.assertIn('NON ÉVALUÉE', msg, msg)
        print('    MW-1 aucune fenetre sans A/E : plus de verdict de biais')

    def test_MW2_le_cas_est_ATTEIGNABLE_par_l_arithmetique_d_A6(self):
        """⚠️⚠️ LE CONTROLE QUI MANQUAIT AU LOT PRECEDENT. On ne pose aucun
        champ : on donne des FENETRES et on laisse les trois champs se
        deduire. Si un futur correctif se place a nouveau APRES la branche
        qui court-circuite, ce test le voit -- l'ancien, non."""
        bt = _backtest_depuis_fenetres(
            [{'ae_ratio': None}, {'ae_ratio': None}])
        # L'etat que la branche VISE, tel qu'A6 le produit reellement :
        self.assertIsNone(bt['ae_cv_wf'])
        self.assertIsNone(bt['ae_moyen_wf'])
        self.assertIsNone(bt['ae_ratio'],
                          "c'est CE couplage qui rendait la branche morte : "
                          "pas d A/E moyen implique pas d A/E de derniere "
                          "fenetre")
        msg = avertissement_walk_forward(bt) or ''
        self.assertIn(
            "AUCUNE fenêtre n'a produit d'A/E", msg,
            f'le cas vise par la branche ne l atteint toujours pas : {msg}')
        print('    MW-2 atteignable depuis les fenetres, pas depuis un dict')

    def test_MW3_second_sens_un_AE_MESURE_a_zero_reste_un_biais(self):
        """⚠️⚠️ LE CAS QUE NI L'AUDITEUR NI MOI N'AVIONS NOMME. `ae_cv` vaut
        aussi `None` quand l'A/E MOYEN vaut exactement 0 (`a6:2085` teste
        `and ae_moyen`, pas `is not None`). Mais un A/E de 0,0 est une valeur
        MESUREE -- le modele attend des sinistres et n'en observe aucun : c'est
        un biais reel, il doit le rester. *Sans ce second sens, le correctif
        de MES-1 rendrait muet un vrai defaut.*"""
        bt = _backtest_depuis_fenetres(
            [{'ae_ratio': 0.0}, {'ae_ratio': 0.0}])
        self.assertIsNone(bt['ae_cv_wf'], 'la fixture ne reproduit plus le cas')
        self.assertIsNotNone(bt['ae_moyen_wf'])
        msg = avertissement_walk_forward(bt) or ''
        self.assertIn('BIAIS DE TARIFICATION', msg,
                      f'un A/E mesure a 0,0 ne se signale plus : {msg}')
        print('    MW-3 A/E mesure a 0,0 : biais, comme il se doit')

    def test_MW4_derniere_fenetre_sans_AE_se_distingue_d_aucune_du_tout(self):
        """⚠️ DEUX ABSENCES DIFFERENTES, DEUX PHRASES. La derniere fenetre sans
        A/E alors que d'autres en ont un n'est pas la meme chose qu'aucune
        fenetre exploitable -- et l'ancienne ligne les confondait toutes deux
        avec un biais."""
        bt = _backtest_depuis_fenetres(
            [{'ae_ratio': 1.01}, {'ae_ratio': 0.99}, {'ae_ratio': None}])
        msg = avertissement_walk_forward(bt) or ''
        self.assertIn('DERNIÈRE FENÊTRE', msg, msg)
        self.assertNotIn('BIAIS DE TARIFICATION', msg)
        self.assertNotIn("AUCUNE fenêtre", msg,
                         'le message confond une derniere fenetre absente '
                         'avec un walk-forward sans aucun A/E')
        print('    MW-4 derniere fenetre absente : phrase distincte')

    def test_MW5_un_message_qui_nomme_une_CAUSE_est_vrai_la_ou_il_tire(self):
        """⚠️⚠️ LE SECOND DEFAUT DE LA BRANCHE. Force a s'executer par un
        backtest assemble a la main, elle affirmait « aucune fenetre n'a
        produit d'A/E exploitable » alors que `ae_ratio` valait 1,00 dans le
        MEME dictionnaire. *Un message qui nomme une cause doit etre vrai dans
        TOUS les etats qui l'atteignent, pas dans celui qu'on avait en tete.*
        """
        bt = dict(_AMONT, ae_ratio=1.00, ae_moyen_wf=1.00, ae_cv_wf=None,
                  n_fenetres=2)
        msg = avertissement_walk_forward(bt) or ''
        self.assertIn('NON MESURÉE', msg, msg)
        self.assertNotIn(
            "AUCUNE fenêtre", msg,
            f"le message affirme qu aucune fenetre n a d A/E alors que "
            f"`ae_ratio` en porte un : {msg}")
        self.assertNotIn("n'a produit d'A/E", msg, msg)
        print('    MW-5 le motif de la branche est vrai la ou elle tire')

    def test_MW6_second_sens_un_walk_forward_sain_reste_muet(self):
        """⚠️ Sans ce controle, une fonction qui avertirait TOUJOURS passerait
        les cinq precedents."""
        bt = _backtest_depuis_fenetres(
            [{'ae_ratio': 0.98}, {'ae_ratio': 1.01}, {'ae_ratio': 0.99}])
        self.assertIsNone(
            avertissement_walk_forward(bt),
            'un walk-forward sain produit un avertissement')
        print('    MW-6 walk-forward sain : muet')

    def test_MW7_le_couplage_dont_depend_le_discriminant_est_pinne(self):
        """⚠️⚠️ SUR QUELLE ASSIETTE ? Le correctif s'appuie sur un fait d'A6 :
        `ae_moyen_wf` et `ae_cv_wf` derivent de LA MEME liste `aes`, donc
        `ae_moyen is None` dit exactement << aucune fenetre n'a d'A/E >>. Si
        quelqu'un les decouplait, le discriminant redeviendrait faux sans
        qu'aucun test de la fonction ne bouge. On epingle le couplage AU SITE,
        par AST."""
        arbre = ast.parse(_A6.read_text(encoding='utf-8'))
        sources = {}
        for n in ast.walk(arbre):
            if not isinstance(n, ast.Assign) or len(n.targets) != 1:
                continue
            cible = n.targets[0]
            if isinstance(cible, ast.Name) and cible.id in (
                    'aes', 'ae_moyen', 'ae_cv'):
                sources.setdefault(cible.id, []).append(n)
        for nom in ('aes', 'ae_moyen', 'ae_cv'):
            self.assertIn(nom, sources,
                          f'`{nom}` a disparu d A6 : le discriminant du '
                          f'correctif MES-1 ne repose plus sur rien')
        src = _A6.read_text(encoding='utf-8')
        for nom in ('ae_moyen', 'ae_cv'):
            for n in sources[nom]:
                seg = ast.get_source_segment(src, n.value) or ''
                self.assertIn(
                    'aes', seg,
                    f'`{nom}` ne derive plus de `aes` ({seg[:60]}) : '
                    f'`ae_moyen_wf is None` ne dit plus << aucune fenetre '
                    f'n a d A/E >>')
        print('    MW-7 `ae_moyen` et `ae_cv` derivent bien de `aes`')


if __name__ == '__main__':
    unittest.main(verbosity=2)
