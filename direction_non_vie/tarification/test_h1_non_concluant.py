"""H1 PUBLIE SON INCERTITUDE ET REFUSE DE CONCLURE SUR DU BRUIT.

Decision de la direction technique du 07/09/2026, prise sur mesure. `H1` tranchait VERT /
AMBRE / ROUGE sur `r = Gini(train)/Gini(test)` calcule sur UN decoupage. Sur
360 tirages -- portefeuille STRICTEMENT inchange, seul l'ordre des lignes
change -- ce statut bascule sur **37 %** des tirages, et la borne du vert
tombe DANS l'intervalle [q05 ; q95] sur 9 cellules sur 9.

⚠️ LA REGLE N'EST PAS INVENTEE : c'est le CINQUIEME CAS DE L'ELASTICITE,
repris tel quel. `estimer_elasticite` publie l'elasticite avec son IC et pose
`concluante = False` quand l'intervalle contient ZERO. Ici la valeur neutre
est **1** : `Gini(train) = Gini(test)`. Un intervalle qui l'enjambe ne dit pas
dans quel sens le modele s'ecarte.

⚠️⚠️ ET LA PREMIERE VERSION N'AURAIT SERVI QU'A UN DOSSIER SUR CINQ. L'IC ne
se calculait que dans `a4._calculer_metriques` -- or `classement[0]`, ce que
H1 evalue, est **32 fois sur 40** la reference GLM d'A3, qui ne passe pas par
la. Mesure : 8 dossiers sur 40 avaient un intervalle. `_stabilite_train` d'A3
le produit desormais aussi, sur ses trois branches.
  *Un correctif pose sur le chemin minoritaire est decoratif : il faut le
  poser la ou la grandeur est reellement produite.*

  NC-1  un sur-apprentissage FRANC donne un intervalle qui exclut 1 ;
  NC-2  un modele STABLE donne un intervalle qui enjambe 1 ;
  NC-3  l'intervalle est REPRODUCTIBLE -- le verdict n'est pas tire au sort ;
  NC-4  H1 publie l'intervalle et dit NON CONCLUANT quand il enjambe 1 ;
  NC-5  second sens : sans enjambement, H1 tranche comme avant ;
  NC-6  sans intervalle, H1 conclut comme avant -- aucune regression ;
  NC-7  l'IC voyage depuis A3, la ou H1 le lit vraiment ;
  NC-8  `ratio_ic` existe sur TOUS les chemins, y compris classement vide.

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
    STATUT_NON_CONCLUANT,
    intervalle_sur_apprentissage,
    surapprentissage_concluant,
)

_A3 = pathlib.Path(_ICI) / 'a3_glm' / 'agent.py'
_A4 = pathlib.Path(_ICI) / 'a4_ml' / 'agent.py'


def _jeux(bruit_test, graine=3, n=600):
    """Un modele dont la prediction est d'autant plus bruitee sur le test.

    `bruit_test = 0` : train et test se ressemblent -> r proche de 1.
    `bruit_test` grand : le test discrimine beaucoup moins -> r >> 1.
    """
    rng = np.random.default_rng(graine)
    y_tr = rng.poisson(0.4, n).astype(float)
    p_tr = y_tr + rng.normal(0, 0.35, n)
    y_te = rng.poisson(0.4, n).astype(float)
    p_te = y_te + rng.normal(0, 0.35 + bruit_test, n)
    return y_tr, p_tr, y_te, p_te


def _h1(modele):
    """H1 par la VRAIE methode d'A4."""
    from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
    agent = AgentA4ML.__new__(AgentA4ML)
    zeros = np.zeros((4, 2))
    val = agent._valider_modele_ml([modele] if modele else [], {'psi': 0.05},
                                   100, 25, zeros, zeros, np.zeros(4))
    return val.get('h1_overfitting', {})


class TestH1NonConcluant(unittest.TestCase):

    def test_NC1_un_surapprentissage_FRANC_exclut_1(self):
        """⚠️ Sans ce sens, une regle qui dirait TOUJOURS << non concluant >>
        passerait NC-2 : on verifie qu'un ecart REEL reste concluant."""
        ic = intervalle_sur_apprentissage(*_jeux(bruit_test=3.0))
        self.assertIsNotNone(ic, 'aucun intervalle sur un cas franc')
        self.assertGreater(ic[0], 1.0,
                           f'un sur-apprentissage franc donne {ic}, qui '
                           f'enjambe 1 : la regle ne conclurait jamais')
        self.assertIs(surapprentissage_concluant(ic), True)
        print(f'    NC-1 sur-apprentissage franc : IC {ic}, exclut 1')

    def test_NC2_un_modele_STABLE_enjambe_1(self):
        ic = intervalle_sur_apprentissage(*_jeux(bruit_test=0.0))
        self.assertIsNotNone(ic)
        self.assertLessEqual(ic[0], 1.0)
        self.assertGreaterEqual(ic[1], 1.0)
        self.assertIs(surapprentissage_concluant(ic), False)
        print(f'    NC-2 modele stable : IC {ic}, enjambe 1')

    def test_NC3_l_intervalle_est_REPRODUCTIBLE(self):
        """⚠️⚠️ LA CONDITION POUR QUE LE VERDICT NE SOIT PAS TIRE AU SORT.
        C'est le reproche exact que l'auditeur independant faisait a l'option
        << seuil relatif a la dispersion >> : elle aurait remplace un verdict
        instable par un verdict instable PLUS CHER, dont la graine devient un
        parametre. Ici, deux executions sur les memes donnees rendent le meme
        intervalle."""
        jeux = _jeux(bruit_test=1.0)
        self.assertEqual(intervalle_sur_apprentissage(*jeux),
                         intervalle_sur_apprentissage(*jeux),
                         "l'intervalle change d'une execution a l'autre : le "
                         "verdict depend de la graine")
        print('    NC-3 deux executions, le meme intervalle')

    def test_NC4_H1_publie_l_intervalle_et_refuse_de_conclure(self):
        h1 = _h1({'modele': 'M', 'gini_test': 0.20, 'gini_train': 0.21,
                  'rmse_test': 0.7, 'overfit_ratio': 1.05,
                  'overfit_ic': (0.85, 1.30)})
        self.assertEqual(h1.get('ratio_ic'), (0.85, 1.30),
                         "l'intervalle n'est pas publie a cote de la mesure")
        self.assertIn('NON CONCLUANT', h1.get('message', ''), h1)
        self.assertIn('0.850', h1.get('message', ''), h1)
        self.assertIn('1.300', h1.get('message', ''), h1)
        # ⚠️⚠️ CE TEST EPINGLAIT `AMBRE`, ET C'ETAIT LA DECISION D'ALORS. Le
        # quatrieme mot a ete arbitre le 07/09/2026, APRES reparation des cinq
        # agregateurs : aucune couleur d'une echelle a trois ne peut porter
        # << je n'ai pas mesure >>, les trois sont des VERDICTS.
        self.assertEqual(h1.get('statut'), STATUT_NON_CONCLUANT, h1)
        print('    NC-4 IC publie, message et statut NON CONCLUANT')

    def test_NC4b_le_quatrieme_mot_ne_devient_JAMAIS_vert_en_amont(self):
        """⚠️⚠️ LA PROPRIETE QUI REND LE QUATRIEME MOT SUR, ET SANS LAQUELLE IL
        MENTIRAIT PLUS FORT QU'AMBRE. Les cinq agregateurs du module ecrivaient
        `... else "VERT"` : un jeton inconnu y tombait et ressortait VERT. Un
        H1 `NON CONCLUANT` aurait donc produit << Modele valide, pret pour la
        production >> sur 88 % des dossiers, en silence et dans la direction
        rassurante.
          *Un mot neuf n'est jamais sur en soi : il l'est quand l'echelle qui
          le recoit refuse de certifier sur ce qu'elle ne reconnait pas.*
        """
        h1_nc = _h1({'modele': 'M', 'gini_test': 0.20, 'gini_train': 0.21,
                     'rmse_test': 0.7, 'overfit_ratio': 1.05,
                     'overfit_ic': (0.85, 1.30)})
        self.assertEqual(h1_nc.get('statut'), STATUT_NON_CONCLUANT)
        # le meme appel rend AUSSI le statut global : on le relit entier
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        agent = AgentA4ML.__new__(AgentA4ML)
        zeros = np.zeros((4, 2))
        val = agent._valider_modele_ml(
            [{'modele': 'M', 'gini_test': 0.20, 'gini_train': 0.21,
              'rmse_test': 0.7, 'overfit_ratio': 1.05,
              'overfit_ic': (0.85, 1.30)}],
            {'psi': 0.05}, 100, 25, zeros, zeros, np.zeros(4))
        self.assertNotEqual(
            val.get('statut_global'), 'VERT',
            "un H1 NON CONCLUANT ressort en statut global VERT : l agregateur "
            "certifie sur un jeton qu il ne reconnait pas")
        self.assertNotIn('Modèle validé', val.get('conclusion', ''),
                         val.get('conclusion'))
        print(f"    NC-4b H1 non concluant -> global "
              f"{val.get('statut_global')}, jamais VERT")

    def test_NC5_second_sens_sans_enjambement_H1_tranche_comme_avant(self):
        """⚠️ Sans ce sens, une regle qui dirait TOUJOURS non concluant
        passerait NC-4 -- et H1 ne dirait plus jamais rien."""
        for gtr, gte, ic, attendu in (
                (0.21, 0.20, (1.02, 1.10), 'VERT'),
                (0.40, 0.20, (1.60, 2.40), 'ROUGE'),
                (0.24, 0.20, (1.15, 1.24), 'AMBRE')):
            with self.subTest(attendu=attendu):
                h1 = _h1({'modele': 'M', 'gini_test': gte, 'gini_train': gtr,
                          'rmse_test': 0.7, 'overfit_ratio': gtr / gte,
                          'overfit_ic': ic})
                self.assertEqual(h1.get('statut'), attendu, h1)
                self.assertNotIn('NON CONCLUANT', h1.get('message', ''))
        print('    NC-5 sans enjambement : VERT / AMBRE / ROUGE inchanges')

    def test_NC6_sans_intervalle_H1_conclut_comme_avant(self):
        """⚠️ CONTRAT D'ABSENCE. Un intervalle non calculable ne doit pas
        rendre H1 muet : il conclut sur le point, comme avant le lot."""
        h1 = _h1({'modele': 'M', 'gini_test': 0.20, 'gini_train': 0.21,
                  'rmse_test': 0.7, 'overfit_ratio': 1.05})
        self.assertIsNone(h1.get('ratio_ic'))
        self.assertEqual(h1.get('statut'), 'VERT', h1)
        self.assertNotIn('NON CONCLUANT', h1.get('message', ''))
        print('    NC-6 sans IC : H1 conclut comme avant')

    def test_NC7_l_IC_voyage_depuis_A3_la_ou_H1_le_lit(self):
        """⚠️⚠️ LE CONTROLE QUI A CHANGE LE LOT. Mesure : `classement[0]` est
        32 fois sur 40 la reference GLM d'A3. Sans l'IC produit PAR A3, la
        decision ne s'appliquait qu'a 8 dossiers sur 40 -- mesure avant
        correction. On epingle donc la chaine par AST : A3 le produit, ses
        metriques le portent, et A4 le relaie dans l'entree GLM."""
        src3 = _A3.read_text(encoding='utf-8')
        arbre3 = ast.parse(src3)
        produit = any(
            isinstance(n, ast.Call)
            and getattr(n.func, 'attr', getattr(n.func, 'id', None))
            == 'intervalle_sur_apprentissage'
            for n in ast.walk(arbre3))
        self.assertTrue(produit,
                        'A3 ne produit plus d intervalle : H1 en sera privé '
                        'sur la majorité des dossiers')
        dicts3 = [n for n in ast.walk(arbre3) if isinstance(n, ast.Dict)
                  and 'overfit_ratio' in {k.value for k in n.keys
                                          if isinstance(k, ast.Constant)}]
        self.assertGreaterEqual(len(dicts3), 3,
                                f'A3 ne porte plus que {len(dicts3)} jeux de '
                                f'metriques avec `overfit_ratio`')
        for d in dicts3:
            cles = {k.value for k in d.keys if isinstance(k, ast.Constant)}
            self.assertIn('overfit_ic', cles,
                          f'un jeu de metriques d A3 (ligne {d.lineno}) publie '
                          f'le ratio SANS son intervalle')
        src4 = _A4.read_text(encoding='utf-8')
        self.assertIn("'overfit_ic':     _met_glm.get('overfit_ic')", src4,
                      "A4 ne relaie plus l IC de la reference GLM : H1 "
                      "l evalue pourtant 32 fois sur 40")
        print(f'    NC-7 A3 produit l IC, ses {len(dicts3)} metriques le '
              f'portent, A4 le relaie')

    def test_NC9_l_intervalle_est_dans_le_MESSAGE_de_chaque_branche(self):
        """⚠️⚠️ LA MOITIE << INFORMATION >>, ET ELLE MANQUAIT. Les services
        impriment `ratio` et `message` : un intervalle qui ne vit que dans le
        CHAMP `ratio_ic` n'atteint aucun document. Mesure du 07/09/2026 sur
        les octets publies : sur les TROIS branches qui CONCLUENT -- VERT,
        AMBRE, ROUGE -- l'intervalle n'apparaissait NULLE PART.
          *Une conclusion publiee sans son incertitude, exactement la ou elle
          compte le plus : la moitie << decision >> livree sans la moitie
          << information >>, et alors les 88 % de non-conclusion sont une
          perte seche.* Trouve par l'auditeur independant.

        ⚠️ On mesure le MESSAGE, pas le champ : c'est le message qui part dans
        le document. Un plant qui vide `_ic_txt` doit rougir ici.
        """
        for gtr, gte, ic, attendu in (
                (0.21, 0.20, (1.02, 1.10), 'VERT'),
                (0.24, 0.20, (1.15, 1.24), 'AMBRE'),
                (0.40, 0.20, (1.60, 2.40), 'ROUGE')):
            with self.subTest(branche=attendu):
                h1 = _h1({'modele': 'M', 'gini_test': gte, 'gini_train': gtr,
                          'rmse_test': 0.7, 'overfit_ratio': gtr / gte,
                          'overfit_ic': ic})
                self.assertEqual(h1.get('statut'), attendu, h1)
                msg = h1.get('message', '')
                self.assertIn(
                    f'{ic[0]:.3f}', msg,
                    f'la branche {attendu} publie une conclusion SANS son '
                    f'intervalle : {msg}')
                self.assertIn(f'{ic[1]:.3f}', msg, msg)
        # ⚠️ ET L'ABSENCE NE LAISSE PAS DE PARENTHESE CREUSE.
        sans = _h1({'modele': 'M', 'gini_test': 0.20, 'gini_train': 0.21,
                    'rmse_test': 0.7, 'overfit_ratio': 1.05})
        self.assertNotIn('IC', sans.get('message', ''), sans)
        print('    NC-9 les 3 branches qui concluent portent leur intervalle')

    def test_NC10_la_graine_et_les_tirages_voyagent_dans_l_audit(self):
        """⚠️⚠️ << GRAINE FIXE >> ETAIT UNE PROPRIETE DU CODE, PAS DU DOSSIER.
        Un verdict produit par reechantillonnage n'est reproductible que si la
        graine et le nombre de tirages sont ecrits A COTE du resultat -- comme
        `format_lu` pour l'arrete, comme la `provenance` de chaque valeur
        reglementaire. *Sans eux, le jour ou la graine change, personne ne
        pourra dire si un statut a bouge pour cette raison.*

        ⚠️ Et ils viennent des CONSTANTES, jamais de litteraux recopies : deux
        nombres pour une seule verite divergeraient au premier ajustement.
        """
        arbre = ast.parse(_A4.read_text(encoding='utf-8'))
        trouve = {}
        for n in ast.walk(arbre):
            if not isinstance(n, ast.Dict):
                continue
            cles = {k.value for k in n.keys if isinstance(k, ast.Constant)}
            if 'audit_id' not in cles or 'agent' not in cles:
                continue
            for k, v in zip(n.keys, n.values):
                if (isinstance(k, ast.Constant)
                        and str(k.value).startswith('ic_surapprentissage')):
                    trouve[k.value] = getattr(v, 'id', None)
        for cle, constante in (
                ('ic_surapprentissage_tirages', 'IC_SURAPPRENTISSAGE_TIRAGES'),
                ('ic_surapprentissage_graine', 'IC_SURAPPRENTISSAGE_GRAINE')):
            with self.subTest(cle=cle):
                self.assertIn(
                    cle, trouve,
                    f'`{cle}` ne figure pas dans la piste d audit d A4 : le '
                    f'verdict bootstrap n est pas reproductible depuis le '
                    f'dossier archive')
                self.assertEqual(
                    trouve[cle], constante,
                    f'`{cle}` est un litteral recopie et non la constante '
                    f'`{constante}` : les deux divergeront')
        print('    NC-10 graine et tirages dans la piste, depuis les constantes')

    def test_NC8_ratio_ic_existe_sur_TOUS_les_chemins(self):
        """⚠️ `_h1_ic` n'etait defini que dans la branche `if classement:` et
        lu par le dictionnaire de sortie, commun aux deux : sur un classement
        VIDE la fonction levait `UnboundLocalError` -- la PANNE, pas
        l'absence. *Une variable publiee doit exister sur tous les chemins qui
        la publient.*"""
        h1 = _h1(None)
        self.assertIn('ratio_ic', h1)
        self.assertIsNone(h1['ratio_ic'])
        self.assertEqual(h1.get('statut'), 'AMBRE')
        print('    NC-8 classement vide : `ratio_ic` present et None')


if __name__ == '__main__':
    unittest.main(verbosity=2)
