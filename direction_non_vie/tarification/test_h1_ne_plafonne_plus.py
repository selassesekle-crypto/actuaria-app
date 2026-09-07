"""H1 NE PLAFONNE PLUS, ET IL LE DIT -- decision du 07/09/2026.

`h1_overfitting` figurait dans les hypotheses PLAFONNANTES d'A6 : son ROUGE
forcait le statut RAG publie a AMBRE en environnement `production`. Or son
verdict se calcule sur un DECOUPAGE UNIQUE. Mesure du 07/09, 360 tirages :
sur un portefeuille STRICTEMENT inchange -- memes contrats, memes sinistres,
seul l'ordre des lignes change -- **il bascule sur 37 % des tirages** (10 % a
55 % selon le plan et la taille), et la borne du VERT tombe DANS l'intervalle
[q05 ; q95] sur 9 cellules sur 9.

    *Un plafond est une affirmation : << ce module ne peut pas etre certifie
    vert >>. Une affirmation dont la valeur depend du tirage n'en est pas une.*

⛔⛔ MAIS LE RETIRER EN SILENCE SERAIT PIRE QUE LE GARDER. Un lecteur qui a
connu H1 plafonnant lirait son silence comme un feu vert : on remplacerait un
faux ROUGE par un faux VERT. La demotion se PUBLIE, avec son motif.

⚠️⚠️ ET J'AI FAILLI LA PUBLIER NULLE PART. `a6.run` rend un dict CONSTRUIT,
pas son `rapport` : poser la cle sur `rapport` ne suffit pas. Mesure de la
SORTIE avant de le voir -- la cle etait ABSENTE du resultat, la reserve
calculee et lue par personne, *exactement le defaut `A1-1`, commis dans le
lot qui devait le nommer*. `HP-4` mesure desormais la SORTIE, pas le cablage.

  HP-1  H1 n'est plus dans les hypotheses plafonnantes ;
  HP-2  un H1 ROUGE ne bloque plus le VERT a lui seul ;
  HP-3  la demotion se PUBLIE des que H1 n'est plus VERT ;
  HP-4  et elle atteint le RESULTAT d'A6, pas seulement son `rapport` ;
  HP-5  second sens : H1 VERT ne produit AUCUNE reserve ;
  HP-6  la reserve nomme le motif chiffre, pas seulement le statut ;
  HP-7  les deux autres hypotheses ML plafonnent TOUJOURS.

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

from core.conformite_reglementaire import (
    reserve_surapprentissage_non_plafonnant,
)

_A6 = pathlib.Path(_ICI) / 'a6_comparaison' / 'agent.py'


def _plafonnantes():
    """Les couples (source, cle) de `_HYP_PLAFONNANTES`, releves PAR AST.

    ⚠️ Au texte, le nom `h1_overfitting` apparait aussi dans les commentaires
    qui EXPLIQUENT son retrait -- un releve au texte compterait la prose du
    correctif comme le defaut qu'il corrige.
    """
    arbre = ast.parse(_A6.read_text(encoding='utf-8'))
    for n in ast.walk(arbre):
        if not (isinstance(n, ast.Assign) and len(n.targets) == 1):
            continue
        cible = n.targets[0]
        if not (isinstance(cible, ast.Name)
                and cible.id == '_HYP_PLAFONNANTES'):
            continue
        couples = []
        for elt in getattr(n.value, 'elts', []):
            if isinstance(elt, ast.Tuple) and len(elt.elts) == 2:
                src, cle = elt.elts
                couples.append((getattr(src, 'id', '?'),
                                getattr(cle, 'value', '?')))
        return couples
    return None


class TestH1NePlafonnePlus(unittest.TestCase):

    def test_HP1_H1_n_est_plus_une_hypothese_plafonnante(self):
        couples = _plafonnantes()
        self.assertIsNotNone(couples,
                             '`_HYP_PLAFONNANTES` est introuvable dans A6')
        self.assertNotIn(
            ('hypotheses_ml', 'h1_overfitting'), couples,
            'H1 plafonne de nouveau le statut publie, alors que son verdict '
            'bascule sur 37 % des tirages a portefeuille inchange')
        print(f'    HP-1 {len(couples)} hypotheses plafonnantes, H1 exclue')

    def test_HP2_un_H1_ROUGE_ne_bloque_plus_le_VERT_a_lui_seul(self):
        """⚠️ On mesure le COMPORTEMENT de la fonction de statut, pas la
        liste : une liste juste avec une lecture fausse ne vaudrait rien."""
        from direction_non_vie.tarification.a6_comparaison.agent import (
            AgentA6Comparaison,
        )
        f = AgentA6Comparaison.__dict__['_calculer_statut_rag']
        agent = object.__new__(AgentA6Comparaison)
        mp = {'modele': 'GLM', 'score_global': 0.85, 'gini_test': 0.28,
              'overfit_ratio': 1.05, 'famille': 'GLM'}
        commun = {
            'profil_valide_par': 'Actuaire',
            'environnement': 'production',
            'cible_est_frequence': True,
            'backtest': {'disponible': True, 'modele_recalibre_fidele': True,
                         'gini_wf_moyen': 0.24, 'ae_ratio': 1.00,
                         'ae_moyen_wf': 1.00, 'ae_cv_wf': 0.02,
                         'n_fenetres': 3, 'n_fenetres_rouge': 0},
            'valide_par_actuaire_dl': True,
            'modele_ampute': False,
            'hypotheses_glm': {'h1_poisson': {'statut': 'VERT'},
                               'h2_homosc': {'statut': 'VERT'},
                               'h5_deviance': {'statut': 'VERT'}},
        }
        vert = {'h1_overfitting': {'statut': 'VERT', 'ratio': 1.02},
                'h2_psi': {'statut': 'VERT'},
                'h4_calibration': {'statut': 'VERT'}}
        rouge = {**vert,
                 'h1_overfitting': {'statut': 'ROUGE', 'ratio': 1.60}}
        s_vert = f(agent, mp, [mp], hypotheses_ml=vert, **commun)
        s_rouge = f(agent, mp, [mp], hypotheses_ml=rouge, **commun)
        self.assertEqual(
            s_vert, s_rouge,
            f'un H1 ROUGE change encore le statut publie ({s_vert} -> '
            f'{s_rouge}) : il plafonne toujours')
        print(f'    HP-2 H1 VERT et H1 ROUGE donnent le meme statut '
              f'({s_rouge})')

    def test_HP3_la_demotion_se_publie_des_que_H1_n_est_plus_VERT(self):
        for statut in ('ROUGE', 'AMBRE'):
            with self.subTest(statut=statut):
                phrase = reserve_surapprentissage_non_plafonnant(
                    {'h1_overfitting': {'statut': statut, 'ratio': 1.6}})
                self.assertIsNotNone(
                    phrase,
                    f'H1 en {statut} ne se declare nulle part : son silence '
                    f'se lira comme un feu vert')
                self.assertIn('NON PLAFONNANT', phrase)
                self.assertIn(statut, phrase)
        print('    HP-3 la demotion se publie sur ROUGE et sur AMBRE')

    def test_HP4_la_reserve_atteint_le_RESULTAT_d_A6_pas_son_rapport(self):
        """⚠️⚠️ LE CONTROLE QUI A MANQUE, ET QUI VIENT DE MORDRE. `a6.run` ne
        rend PAS son `rapport` : il construit un dict, et une cle absente de
        cette construction n'existe pas pour les services. On exige donc que
        la cle figure dans CHACUN des dicts rendus -- releve par AST, pas par
        `in` sur le texte, qui compterait aussi les commentaires."""
        # ⚠️⚠️ TOUT DICT QUI PORTE LES RESERVES, PAS SEULEMENT LES `return`.
        # Ma premiere version ne regardait que `ast.Return` : elle n'en voyait
        # qu'UN sur les deux, et le second -- `_tmp_a6 = {...}`, le payload du
        # rapport d'equipe -- restait NON GARDE. *Une assiette qui ne couvre
        # que la moitie des surfaces laisse l'autre moitie diverger.*
        arbre = ast.parse(_A6.read_text(encoding='utf-8'))
        rendus = []
        for n in ast.walk(arbre):
            if not isinstance(n, ast.Dict):
                continue
            cles = {k.value for k in n.keys if isinstance(k, ast.Constant)}
            if 'reserve_bases_gini' in cles:
                rendus.append((n.lineno, cles))
        self.assertGreaterEqual(
            len(rendus), 2,
            f'A6 ne porte plus que {len(rendus)} surface(s) de reserves : la '
            f'forme du resultat a change, ce controle est aveugle')
        for ligne, cles in rendus:
            self.assertIn(
                'reserve_surapprentissage', cles,
                f'le dict rendu a a6:{ligne} publie les autres reserves mais '
                f'PAS la demotion de H1 : elle serait calculee et lue par '
                f'personne')
        print(f'    HP-4 la cle est dans les {len(rendus)} surfaces d A6')

    def test_HP5_second_sens_un_H1_VERT_ne_produit_AUCUNE_reserve(self):
        """⚠️ Sans ce sens, une reserve PERMANENTE passerait HP-3 -- et une
        reserve permanente n'est plus lue."""
        for hyp in ({'h1_overfitting': {'statut': 'VERT', 'ratio': 1.01}},
                    {'h1_overfitting': {}}, {}, None):
            with self.subTest(hyp=hyp):
                self.assertIsNone(
                    reserve_surapprentissage_non_plafonnant(hyp),
                    'une reserve est publiee alors que H1 est VERT ou absent')
        print('    HP-5 H1 VERT ou absent : aucune reserve')

    def test_HP6_la_reserve_nomme_le_MOTIF_chiffre(self):
        """⚠️ << H1 ne plafonne plus >> sans le motif se lit comme un
        relachement arbitraire. Le chiffre qui l'a decide doit y etre."""
        phrase = reserve_surapprentissage_non_plafonnant(
            {'h1_overfitting': {'statut': 'ROUGE', 'ratio': 1.6}})
        self.assertIn('37 %', phrase, phrase)
        self.assertIn('DÉCOUPAGE UNIQUE', phrase, phrase)
        self.assertIn('1.600', phrase,
                      'le ratio mesure ne figure pas dans la reserve')
        print('    HP-6 la reserve porte son motif chiffre')

    def test_HP8_la_cle_publiee_est_ALIMENTEE_par_le_socle(self):
        """⚠️⚠️ LE SECOND TROU, TROUVE PAR UN PLANT MUET. `HP-4` verifie que la
        cle FIGURE dans les dicts rendus -- pas qu'elle contient quelque
        chose. Un plant qui remplacait l'appel du socle par une lambda rendant
        `None` laissait tout VERT : la cle etait la, vide.
          *Une cle publiee et jamais alimentee est exactement le defaut
          `A1-1` -- calcule d'un cote, lu de l'autre, rien au milieu.*

        On suit donc la CHAINE par AST : la valeur posee sur
        `rapport['reserve_surapprentissage']` doit venir d'un nom assigne par
        un appel a `reserve_surapprentissage_non_plafonnant`.
        """
        arbre = ast.parse(_A6.read_text(encoding='utf-8'))
        # 1. quel nom est pose sur la cle publiee ?
        pose = None
        for n in ast.walk(arbre):
            if not (isinstance(n, ast.Assign) and len(n.targets) == 1):
                continue
            c = n.targets[0]
            if (isinstance(c, ast.Subscript)
                    and isinstance(c.slice, ast.Constant)
                    and c.slice.value == 'reserve_surapprentissage'):
                pose = getattr(n.value, 'id', None)
        self.assertIsNotNone(
            pose,
            "aucune affectation `rapport['reserve_surapprentissage'] = <nom>` "
            "dans A6 : la reserve n est jamais posee")
        # 2. ce nom vient-il bien d'un appel au socle ?
        alimente = False
        for n in ast.walk(arbre):
            if not (isinstance(n, ast.Assign) and len(n.targets) == 1):
                continue
            c = n.targets[0]
            if not (isinstance(c, ast.Name) and c.id == pose):
                continue
            if not isinstance(n.value, ast.Call):
                continue
            f = n.value.func
            nom = (f.attr if isinstance(f, ast.Attribute)
                   else getattr(f, 'id', None))
            if nom == 'reserve_surapprentissage_non_plafonnant':
                alimente = True
        self.assertTrue(
            alimente,
            f'`{pose}` est publie mais ne vient pas de '
            f'`reserve_surapprentissage_non_plafonnant` : la cle existe et '
            f'reste vide')
        print(f'    HP-8 `{pose}` vient bien du socle, et il est publie')

    def test_HP7_les_deux_autres_hypotheses_ML_plafonnent_TOUJOURS(self):
        """⚠️⚠️ LE SECOND SENS DU RETRAIT. Retirer H1 ne doit pas avoir
        desarme ses voisines : `h2_psi` (derive reelle des features) et
        `h4_calibration` ne dependent PAS d'un decoupage unique."""
        couples = _plafonnantes() or []
        for cle in ('h2_psi', 'h4_calibration'):
            with self.subTest(cle=cle):
                self.assertIn(
                    ('hypotheses_ml', cle), couples,
                    f'`{cle}` ne plafonne plus : le retrait de H1 a emporte '
                    f'une voisine qui, elle, ne mesure pas du bruit')
        for cle in ('h1_poisson', 'h2_homosc', 'h5_deviance'):
            with self.subTest(cle=cle):
                self.assertIn(('hypotheses_glm', cle), couples)
        print('    HP-7 les 5 autres hypotheses plafonnent toujours')


if __name__ == '__main__':
    unittest.main(verbosity=2)
