"""Controles positifs — `a4/C10`, suite : le meilleur de chaque base.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
A6 choisissait -- et choisit toujours -- son modele de production par UN tri
global sur `score_global`. Quand le catalogue melange des bases de Gini
differentes, ce tri compare des nombres qui ne mesurent pas la meme chose :
mesure, +18,1 % en faveur de la base comptage des que l'exposition varie, et
0,0 % a exposition constante.

CE LOT N'ENLEVE RIEN AU TRI GLOBAL. Il AJOUTE :
  · `meilleur_par_base` -- une ligne par base, le meilleur de chacune ;
  · `arbitrage_contestable` -- la phrase qui dit que le choix automatique
    tient, sans etre pour autant etabli.

⚠️⚠️ POURQUOI CE N'EST PAS `finalistes_par_base`. Mesure sur le catalogue
reel de 9 modeles : GLM_POISSON (comptage) 1,0000 contre 0,1912 pour le
meilleur unitaire. Ce ne sont pas deux finalistes -- c'est un gagnant et un
second lointain. *Une etiquette qui affirme une egalite que les chiffres ne
montrent pas est le defaut que cet audit poursuit.*

⚠️ AUCUN SEUIL DE PROXIMITE, ET C'EST UN CHOIX. On presente TOUJOURS le
meilleur de chaque base -- meme regle qu'`alternatives`, qui montre les trois
suivants sans condition. Le score etant normalise par le gagnant, un ecart de
10 % ne veut pas la meme chose selon la dispersion : fixer une coupure serait
fabriquer un nombre.

⚠️ ET RIEN NE BLOQUE. `modele_production` reste choisi automatiquement : un
fail-safe qui met la chaine hors service n'est pas un fail-safe.
"""

from __future__ import annotations

import unittest

from core.conformite_reglementaire import (
    BASE_GINI_COMPTAGE,
    BASE_GINI_COUT_MOYEN,
    BASE_GINI_UNITAIRE,
    meilleur_par_base,
    reserve_arbitrage_contestable,
)


def _m(nom, base, score, gini=0.2):
    return {'modele': nom, 'base_gini': base, 'score_global': score,
            'gini_test': gini}


#: un classement DEJA TRIE, comme celui qu'A6 construit
_CLASSEMENT = [
    _m('GLM_POISSON', BASE_GINI_COMPTAGE, 1.0000, 0.0962),
    _m('ML_LINEAIRE', BASE_GINI_UNITAIRE, 0.1912, -0.0389),
    _m('ML_XGBOOST', BASE_GINI_UNITAIRE, -0.0698, -0.0683),
    _m('DL_CANN', BASE_GINI_COMPTAGE, -0.1498, -0.1103),
]


class TestMeilleurParBase(unittest.TestCase):
    """Une ligne par base, le rang publie, et aucun choix modifie."""

    # ══════════════════════════════════════════════════════════════════════
    # ① UNE LIGNE PAR BASE — LE MEILLEUR DE CHACUNE
    # ══════════════════════════════════════════════════════════════════════

    def test_une_seule_ligne_par_base_et_c_est_LA_MEILLEURE(self):
        res = meilleur_par_base(_CLASSEMENT, _CLASSEMENT[0])
        self.assertEqual(len(res), 2, "2 bases au classement, 2 lignes attendues")
        par_base = {x['base']: x for x in res}
        self.assertEqual(par_base[BASE_GINI_COMPTAGE]['modele'], 'GLM_POISSON')
        self.assertEqual(
            par_base[BASE_GINI_UNITAIRE]['modele'], 'ML_LINEAIRE',
            "La ligne unitaire doit porter le MEILLEUR unitaire (0,1912), pas "
            "le premier rencontré ni le dernier.")

    def test_le_rang_global_est_publie_a_cote_du_score(self):
        """⚠️ Sans lui, deux lignes se liraient à égalité alors que l'une est
        2ᵉ et l'autre 9ᵉ. Le score est normalisé par le gagnant."""
        res = meilleur_par_base(_CLASSEMENT, _CLASSEMENT[0])
        rangs = {x['modele']: x['rang_global'] for x in res}
        self.assertEqual(rangs['GLM_POISSON'], 1)
        self.assertEqual(rangs['ML_LINEAIRE'], 2)

    def test_une_base_NON_DECLAREE_a_sa_propre_ligne(self):
        """⚠️ Jamais fondue dans une autre : ne pas savoir n'est pas savoir."""
        classement = [*_CLASSEMENT, _m('INCONNU', None, -0.9)]
        res = meilleur_par_base(classement, _CLASSEMENT[0])
        sans_base = [x for x in res if x['base'] is None]
        self.assertEqual(len(sans_base), 1)
        self.assertIn('NON DÉCLARÉE', sans_base[0]['base_libelle'])
        self.assertEqual(sans_base[0]['modele'], 'INCONNU')

    def test_trois_bases_donnent_trois_lignes(self):
        classement = [*_CLASSEMENT, _m('GLM_GAMMA', BASE_GINI_COUT_MOYEN, -0.5)]
        self.assertEqual(len(meilleur_par_base(classement, _CLASSEMENT[0])), 3)

    # ══════════════════════════════════════════════════════════════════════
    # ② `est_retenu` SE DÉRIVE — jamais écrit à la main
    # ══════════════════════════════════════════════════════════════════════

    def test_est_retenu_suit_le_modele_de_production(self):
        """⚠️ SECOND SENS PLANTÉ : on change le modèle de production et le
        drapeau doit suivre. Un booléen posé à la main deviendrait faux le
        jour où le choix change ailleurs.
        """
        res = meilleur_par_base(_CLASSEMENT, _CLASSEMENT[0])
        self.assertEqual([x['modele'] for x in res if x['est_retenu']],
                         ['GLM_POISSON'])

        autre = meilleur_par_base(_CLASSEMENT, _CLASSEMENT[1])
        self.assertEqual([x['modele'] for x in autre if x['est_retenu']],
                         ['ML_LINEAIRE'],
                         "`est_retenu` ne suit plus le modèle de production : "
                         "il est écrit au lieu d'être dérivé.")

    def test_aucun_retenu_si_le_modele_de_production_est_absent(self):
        """Second sens : on n'invente pas un retenu quand rien ne l'est."""
        res = meilleur_par_base(_CLASSEMENT, None)
        self.assertEqual([x for x in res if x['est_retenu']], [])

    # ══════════════════════════════════════════════════════════════════════
    # ③ AUCUN SEUIL DE PROXIMITÉ — c'est le cœur du design
    # ══════════════════════════════════════════════════════════════════════

    def test_une_base_lointaine_est_presentee_QUAND_MEME(self):
        """⚠️⚠️ LE TEST QUI FIGE LA DÉCISION DE CONCEPTION.

        Le second est à 0,1912 contre 1,0000 — un écart énorme. Il doit
        FIGURER, sans condition. *L'actuaire juge la proximité ; le code ne
        l'invente pas.* Si une coupure apparaissait un jour, ce test tombe.
        """
        loin = [_CLASSEMENT[0], _m('ML_TRES_LOIN', BASE_GINI_UNITAIRE, -9.99)]
        res = meilleur_par_base(loin, loin[0])
        self.assertEqual(len(res), 2)
        self.assertIn('ML_TRES_LOIN', [x['modele'] for x in res])
        self.assertIsNotNone(reserve_arbitrage_contestable(res, loin[0]))

    def test_une_seule_base_ne_declenche_aucune_reserve(self):
        """Second sens : rien à contester, donc rien à dire. Une réserve qui
        se déclenche toujours n'informe plus de rien."""
        une = [_CLASSEMENT[0], _m('DL_CANN', BASE_GINI_COMPTAGE, -0.15)]
        res = meilleur_par_base(une, une[0])
        self.assertEqual(len(res), 1)
        self.assertIsNone(reserve_arbitrage_contestable(res, une[0]))

    def test_un_classement_vide_ne_leve_pas(self):
        self.assertEqual(meilleur_par_base([], None), [])
        self.assertEqual(meilleur_par_base(None, None), [])
        self.assertIsNone(reserve_arbitrage_contestable([], None))

    # ══════════════════════════════════════════════════════════════════════
    # ④ LA RÉSERVE DIT CE QU'IL FAUT, ET NE BLOQUE RIEN
    # ══════════════════════════════════════════════════════════════════════

    def test_la_reserve_nomme_les_bases_les_scores_et_les_rangs(self):
        res = meilleur_par_base(_CLASSEMENT, _CLASSEMENT[0])
        texte = reserve_arbitrage_contestable(res, _CLASSEMENT[0])
        for attendu in ('GLM_POISSON', 'ML_LINEAIRE', 'comptage prédit',
                        'rang 1', 'rang 2', '18,1 %', 'normalisé par le gagnant'):
            self.assertIn(attendu, texte)

    def test_aucun_choix_n_est_modifie_par_ce_lot(self):
        """⚠️⚠️ LA CONDITION DU LOT, contrôlée par AST.

        `modele_production` doit rester `classement[0]` — le tri global décide
        toujours seul. Si ce lot avait glissé vers un choix par base, un prix
        aurait pu bouger sans que rien ne le dise.
        """
        import ast
        import inspect
        import textwrap

        from direction_non_vie.tarification.a6_comparaison import agent as mod

        src = textwrap.dedent(inspect.getsource(mod.AgentA6Comparaison.run))
        arbre = ast.parse(src)
        choix = [
            ast.unparse(n.value) for n in ast.walk(arbre)
            if isinstance(n, ast.Assign)
            and ast.unparse(n.targets[0]) == 'modele_production'
        ]
        self.assertEqual(
            choix, ['classement[0]'],
            f"Le modèle de production n'est plus le premier du classement "
            f"global : {choix}. Ce lot ne devait RIEN changer au choix.")

    def test_la_reserve_est_publiee_dans_l_excel(self):
        import inspect

        from direction_non_vie.tarification.services import tarif_excel

        src = inspect.getsource(tarif_excel)
        self.assertIn('arbitrage_contestable', src)
        self.assertIn('Arbitrage contestable', src)


if __name__ == '__main__':
    unittest.main()
