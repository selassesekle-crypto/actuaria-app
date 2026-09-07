"""UNE SEULE ORIENTATION POUR LE SUR-APPRENTISSAGE -- constat `A5-1`.

Le socle `ratio_sur_apprentissage` se declare << SOURCE UNIQUE DE LA FORMULE >>
et rend ``Gini(train) / Gini(test)``. `a4._valider_modele_ml` calculait la
RECIPROQUE en ligne, sans passer par lui. Le meme rapport signe publiait donc,
a trois lignes d'ecart :

    overfit=1.250                       <- train / test
    Overfit ratio : 1.250               <- train / test
    H1 Overfitting : AMBRE | ratio=0.8  <- test / train

*Deux ecritures du meme fait, sans que rien ne dise laquelle se lit dans quel
sens.* Et l'entree `xgboost_optuna`, construite a la main a cote de la fabrique
commune, mettait elle aussi `Gini(test)/Gini(train)` sous la cle
`overfit_ratio` -- d'ou `a6` tire 30 % du score de selection.

  OS-1  plus aucun site ne divise deux Gini a la main ;
  OS-2  H1 et le classement publient la MEME orientation, mesuree ;
  OS-3  la severite n'a pas bouge : identique a l'ancienne regle sur toute
        entree FINIE (c'est l'arbitrage << B-zero >>) ;
  OS-4  les seuils sont des constantes NOMMEES du socle ;
  OS-5  un classement vide ne publie plus 1.0 / 0.0 / 0.0 ;
  OS-6  l'entree Optuna porte le meme jeu de cles que les autres ;
  OS-7  un Gini de test <= 0 reste ROUGE (arbitrage du lot 4).

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""

from __future__ import annotations

import ast
import math
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
    SEUIL_SURAPPRENTISSAGE_ALERTE,
    SEUIL_SURAPPRENTISSAGE_AMBRE,
    SEUIL_SURAPPRENTISSAGE_VERT,
    ratio_sur_apprentissage,
)

_A4 = pathlib.Path(_ICI) / 'a4_ml' / 'agent.py'


def _h1(modele):
    """H1 par la VRAIE methode -- jamais une copie de sa logique."""
    from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
    agent = AgentA4ML.__new__(AgentA4ML)
    zeros = np.zeros((4, 2))
    val = agent._valider_modele_ml([modele] if modele else [], {'psi': 0.05},
                                   100, 25, zeros, zeros, np.zeros(4))
    return val.get('h1_overfitting', {})


class TestOrientationUnique(unittest.TestCase):

    def test_OS1_plus_aucun_site_ne_divise_deux_Gini_a_la_main(self):
        """⚠️ PAR AST, et sur TOUT le depot. Un releve au texte prendrait les
        commentaires qui EXPLIQUENT le defaut pour le defaut lui-meme.

        ⚠️⚠️ MA PREMIERE VERSION NE RECONNAISSAIT QUE LES NOMS `gini_train` ET
        `gini_test` -- LE RELEVE PAR SYMBOLE, DANS MON PROPRE CONTROLE. Un
        plant qui remettait `gini_opt / max(gini_train_opt, 1e-6)` a l'entree
        Optuna la laissait **VERTE** : le site ne nomme pas ses variables
        comme je les cherchais. *Un controle qui cherche des noms exacts ne
        surveille que le vocabulaire que j'avais en tete.*

        Le critere est desormais SEMANTIQUE : une division dont les DEUX
        cotes parlent de `gini` et dont au moins un parle de `train`. Il
        laisse passer les vraies normalisations -- `gini_test / max_gini`,
        `variation_gini / gini_reference` -- qui ne comparent pas
        l'entrainement au test.
        """
        fautifs = []
        for chemin in sorted(pathlib.Path(_RACINE).rglob('*.py')):
            s = chemin.as_posix()
            if ('.venv' in s or '/audit_2026_08/' in s
                    or 'Python/pythoncore' in s
                    or chemin.name.startswith('test_')):
                continue
            source = chemin.read_text(encoding='utf-8', errors='replace')
            try:
                arbre = ast.parse(source)
            except SyntaxError:                     # pragma: no cover
                continue
            for n in ast.walk(arbre):
                if not (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)):
                    continue
                gauche = (ast.get_source_segment(source, n.left) or '').lower()
                droite = (ast.get_source_segment(source, n.right) or '').lower()
                if ('gini' in gauche and 'gini' in droite
                        and ('train' in gauche or 'train' in droite)):
                    fautifs.append(f'{chemin.relative_to(_RACINE).as_posix()}'
                                   f':{n.lineno}')
        # Le socle a le droit -- c'est LUI la formule.
        fautifs = [f for f in fautifs
                   if not f.startswith('core/conformite_reglementaire.py')]
        self.assertEqual(
            fautifs, [],
            f'un ratio de Gini est encore calcule hors du socle : {fautifs}')
        print('    OS-1 le socle est le seul a diviser deux Gini')

    def test_OS2_H1_et_le_classement_publient_la_MEME_orientation(self):
        """⚠️⚠️ LE CONTROLE QUI COMPTE, ET IL SE MESURE. On donne a H1 une
        entree de classement dont `overfit_ratio` est celui du socle, et on
        exige que le ratio publie par H1 soit LE MEME NOMBRE -- pas sa
        reciproque. Avant le correctif, H1 rendait 0,8 quand la ligne du
        dessus affichait 1,25."""
        gtr, gte = 0.30, 0.24
        attendu = ratio_sur_apprentissage(gtr, gte)          # 1,25
        h1 = _h1({'modele': 'ML_GBM', 'gini_test': gte, 'gini_train': gtr,
                  'rmse_test': 0.7, 'overfit_ratio': round(attendu, 3)})
        self.assertIsNotNone(h1.get('ratio'))
        self.assertAlmostEqual(
            h1['ratio'], attendu, places=3,
            msg=f"H1 publie {h1['ratio']} quand le classement publie "
                f"{attendu:.3f} : les deux surfaces du meme rapport donnent "
                f"deux ecritures du meme fait")
        self.assertIn('train/test', h1.get('titre_graphique', ''))

        # ⚠️⚠️ LES TROIS BRANCHES, PAS UNE SEULE. Ma premiere version ne
        # lisait que le message rendu par CETTE fixture -- c'est-a-dire la
        # branche AMBRE. Un plant qui remettait `test/train` dans le libelle
        # de la branche VERTE la laissait **VERTE** : le controle ne visitait
        # pas la ligne plantee. *Un libelle se verifie sur chaque branche qui
        # peut le publier, pas sur celle que la fixture atteint.*
        for gtr, gte, attendu_statut in ((0.20, 0.20, 'VERT'),
                                         (0.30, 0.24, 'AMBRE'),
                                         (0.40, 0.24, 'ROUGE')):
            with self.subTest(statut=attendu_statut):
                h = _h1({'modele': 'M', 'gini_test': gte, 'gini_train': gtr,
                         'rmse_test': 0.7, 'overfit_ratio': None})
                self.assertEqual(h.get('statut'), attendu_statut, h)
                self.assertIn(
                    'train/test', h.get('message', ''),
                    f"la branche {attendu_statut} ne nomme pas l orientation "
                    f"de sa grandeur : {h.get('message')}")
                self.assertNotIn(
                    'test/train', h.get('message', ''),
                    f"la branche {attendu_statut} annonce la RECIPROQUE de ce "
                    f"qu elle publie : {h.get('message')}")
        print(f"    OS-2 H1 et le classement disent tous deux "
              f"{h1['ratio']:.3f}, sur les 3 branches")

    def test_OS3_la_severite_n_a_pas_bouge_sur_toute_entree_FINIE(self):
        """⚠️⚠️ L'ARBITRAGE << B-ZERO >> SE MESURE. Les seuils sont TRANSPORTES,
        pas rejoues : `test/train >= 0.90` s'ecrit `train/test <= 1/0.90`. On
        rejoue l'ANCIENNE regle -- ecrite ici comme SPECIFICATION a preserver,
        c'est un test de caracterisation -- et on exige l'egalite sur une
        grille qui couvre les deux cotes du seuil et les cas degeneres finis.

        ⚠️ Les entrees NON FINIES sont exclues, et c'est mesure : sur `nan`
        l'ancienne regle rendait ROUGE, sur `gini_test = inf` elle rendait
        **VERT** (<< Pas d'overfitting >> sur un Gini infini). Le correctif
        les declare non mesurables. *Ce sont les seules divergences, et elles
        vont toutes vers l'aveu.*
        """
        def ancienne(gtr, gte):
            r = (gte / gtr if gte is not None and gtr is not None and gtr > 0
                 else None)
            if r is None:
                return 'AMBRE'
            return 'VERT' if r >= 0.90 else 'AMBRE' if r >= 0.80 else 'ROUGE'

        valeurs = [None, -0.5, -0.01, 0.0, 0.001, 0.05, 0.1, 0.15, 0.2,
                   0.222, 0.25, 0.26, 0.3, 0.5, 0.9]
        ecarts = []
        for gtr in valeurs:
            for gte in valeurs:
                h1 = _h1({'modele': 'M', 'gini_test': gte, 'gini_train': gtr,
                          'rmse_test': 0.7, 'overfit_ratio': None})
                if h1.get('statut') != ancienne(gtr, gte):
                    ecarts.append((gtr, gte, ancienne(gtr, gte),
                                   h1.get('statut')))
        self.assertEqual(
            ecarts, [],
            f'la severite a bouge sur {len(ecarts)} combinaison(s) FINIES : '
            f'{ecarts[:6]} — l arbitrage etait << 0 bascule >>')
        print(f'    OS-3 {len(valeurs) ** 2} combinaisons finies, 0 bascule')

    def test_OS4_les_seuils_sont_des_constantes_NOMMEES_du_socle(self):
        """⚠️ Quatre nombres vivaient en litteraux pour UNE propriete, dans
        DEUX orientations : `1.15` (classement), `0.85` (Optuna, qui n'est
        meme pas la reciproque exacte -- 1/1,15 = 0,8696), `0.90` et `0.80`
        (H1, orientation inverse). On verifie qu'aucun ne subsiste."""
        self.assertAlmostEqual(SEUIL_SURAPPRENTISSAGE_VERT, 1 / 0.90, places=6)
        self.assertAlmostEqual(SEUIL_SURAPPRENTISSAGE_AMBRE, 1.25, places=6)
        self.assertAlmostEqual(SEUIL_SURAPPRENTISSAGE_ALERTE, 1.15, places=6)

        source = _A4.read_text(encoding='utf-8')
        arbre = ast.parse(source)
        fautifs = []
        # ⚠️⚠️ ON LIT LA COMPARAISON, PAS LA LIGNE PHYSIQUE. Ma premiere
        # version cherchait le litteral puis regardait si SA LIGNE contenait
        # << overfit >>. Un plant qui remettait `1.15` sur une ligne de
        # continuation -- `else met['overfit_ratio']` puis `> 1.15)` -- la
        # laissait **VERTE** : le litteral et le nom vivaient sur deux lignes.
        # *Une expression n'a pas de numero de ligne ; c'est l'arbre qui la
        # porte, pas la mise en page.*
        for n in ast.walk(arbre):
            if not isinstance(n, ast.Compare):
                continue
            seg = (ast.get_source_segment(source, n) or '').lower()
            if 'overfit_ratio' not in seg and 'ratio_of' not in seg:
                continue
            # ⚠️⚠️ UN LITTERAL PEUT SE DEGUISER EN CALCUL. Ma deuxieme version
            # n'acceptait que `ast.Constant` comme comparateur : un plant qui
            # ecrivait `<= 1 / 0.90` -- un `BinOp` de deux litteraux, donc
            # exactement le nombre en dur qu'on veut interdire -- la laissait
            # **VERTE**. On refuse desormais TOUT comparateur qui porte un
            # nombre, si profond soit-il dans son arbre.
            for c in n.comparators:
                for sous in ast.walk(c):
                    if (isinstance(sous, ast.Constant)
                            and isinstance(sous.value, (int, float))
                            and not isinstance(sous.value, bool)):
                        fautifs.append(f'a4:{n.lineno}: {seg[:70]}')
                        break
        self.assertEqual(
            fautifs, [],
            f'un seuil de sur-apprentissage est encore un litteral dans A4 : '
            f'{fautifs}')
        print('    OS-4 les trois seuils sont nommes, aucun litteral restant')

    def test_OS5_un_classement_VIDE_ne_publie_plus_1_0_et_deux_zeros(self):
        """⚠️⚠️ LE LITTERAL NEUTRE, cause (a), au milieu du bloc corrige pour
        une autre raison. `ratio_of, gini_test, gini_train = 1.0, 0.0, 0.0`
        publiait la stabilite PARFAITE et deux Gini nuls pour un modele qui
        n'existe pas. Le statut, lui, etait honnete -- ce qui rendait les
        trois chiffres d'autant plus credibles."""
        h1 = _h1(None)
        self.assertEqual(h1.get('statut'), 'AMBRE')
        for cle in ('ratio', 'gini_test', 'gini_train'):
            self.assertIsNone(
                h1.get(cle),
                f'`{cle}` vaut {h1.get(cle)!r} sur un classement VIDE : '
                f'une mesure fabriquee pour un modele qui n existe pas')
        print('    OS-5 classement vide : trois absences, zero litteral')

    def test_OS6_l_entree_Optuna_porte_le_MEME_jeu_de_cles(self):
        """⚠️⚠️ TROIS DEFAUTS D'UNE SEULE CAUSE : l'entree etait ecrite a la
        main a cote de la fabrique commune. Il lui manquait `recommandation`,
        que `a4:2481` lit SANS garde -- donc `optuna_trials > 0` faisait
        echouer A4 en ENTIER (`KeyError`), mesure par execution. Le plantage
        le plus visible masquait le plus grave : l'orientation."""
        arbre = ast.parse(_A4.read_text(encoding='utf-8'))
        jeux = []
        for n in ast.walk(arbre):
            if not (isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'append'
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == 'classement'
                    and n.args and isinstance(n.args[0], ast.Dict)):
                continue
            cles = {k.value for k in n.args[0].keys
                    if isinstance(k, ast.Constant)}
            if 'overfit_ratio' in cles:
                jeux.append((n.lineno, cles))
        self.assertGreaterEqual(len(jeux), 3,
                                f'moins de trois fabriques trouvees : {jeux}')
        commun = set.intersection(*[c for _, c in jeux])
        for ligne, cles in jeux:
            manquantes = commun - cles
            self.assertEqual(
                manquantes, set(),
                f'l entree construite a a4:{ligne} n a pas {manquantes}')
        self.assertIn('recommandation', commun,
                      'la cle que `a4:2481` lit sans garde a disparu du '
                      'jeu commun : le KeyError peut revenir')
        print(f'    OS-6 {len(jeux)} fabriques, jeu de cles commun de '
              f'{len(commun)}')

    def test_OS7_un_Gini_de_TEST_negatif_reste_ROUGE(self):
        """⚠️ ARBITRAGE DEJA PRIS (Selasse, lot 4, point 4) : le socle rendrait
        << non mesurable >> ; ici ce serait une regression. Un Gini de test
        <= 0 dit que le modele ne discrimine pas sur son jeu d'evaluation."""
        for gte in (-0.05, 0.0):
            with self.subTest(gini_test=gte):
                h1 = _h1({'modele': 'M', 'gini_test': gte, 'gini_train': 0.25,
                          'rmse_test': 0.7, 'overfit_ratio': None})
                self.assertEqual(h1.get('statut'), 'ROUGE', h1)
                self.assertNotIn('NON MESURABLE',
                                 h1.get('message', '').upper(), h1)
        # ⚠️ ET LE SECOND SENS : un Gini d'ENTRAINEMENT <= 0, lui, reste
        # NON MESURABLE -- rien n'a ete appris, il n'y a pas de rapport.
        h1 = _h1({'modele': 'M', 'gini_test': 0.20, 'gini_train': -0.02,
                  'rmse_test': 0.7, 'overfit_ratio': None})
        self.assertEqual(h1.get('statut'), 'AMBRE', h1)
        self.assertIn('NON MESURABLE', h1.get('message', '').upper(), h1)
        print('    OS-7 test <= 0 ROUGE, train <= 0 NON MESURABLE')

    def test_OS8_le_socle_refuse_ce_que_H1_doit_traiter_AVANT_lui(self):
        """⚠️ Le contrat du socle et celui de H1 ne coincident pas, et c'est
        DELIBERE : `ratio_sur_apprentissage` rend `None` sur `gini_test <= 0`,
        la ou H1 doit rendre ROUGE. Si le socle changeait d'avis, H1
        deviendrait silencieusement plus laxiste."""
        self.assertIsNone(ratio_sur_apprentissage(0.25, 0.0))
        self.assertIsNone(ratio_sur_apprentissage(0.25, -0.05))
        self.assertIsNone(ratio_sur_apprentissage(None, 0.2))
        self.assertIsNone(ratio_sur_apprentissage(float('nan'), 0.2))
        self.assertAlmostEqual(ratio_sur_apprentissage(0.30, 0.24), 1.25,
                               places=6)
        self.assertTrue(math.isfinite(ratio_sur_apprentissage(0.3, 0.24)))
        print('    OS-8 le contrat du socle est celui sur lequel H1 s appuie')


if __name__ == '__main__':
    unittest.main(verbosity=2)
