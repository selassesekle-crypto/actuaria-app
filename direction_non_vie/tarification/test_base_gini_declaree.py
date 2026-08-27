"""Controles positifs — constat `a4/C10` : chaque Gini declare SA BASE.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
Un Gini est un indice de CONCORDANCE : il trie par la prediction et cumule
l'observe. Deux modeles qui trient sur des grandeurs differentes ne rendent
donc pas le meme nombre, meme a qualite identique.

MESURE le 27/08/2026 sur un portefeuille a exposition variable :
    base COMPTAGE 0,4339 · base UNITAIRE 0,3675  -> +18,1 %
    a exposition CONSTANTE, l'ecart tombe a 0,0000
L'ecart vient donc ENTIEREMENT de la variation d'exposition, et il est
SYSTEMATIQUEMENT favorable a la base comptage. A6 trie sur `gini_test`,
pondere 40 % : la convention non mesuree flatte un camp.

⚠️⚠️ CE LOT NE CORRIGE RIEN, IL DECLARE. Aligner les bases changerait un Gini
publie, donc potentiellement le modele retenu, donc UN PRIX -- et cela demande
une vraie decision sur ce que « rang de risque » doit signifier. Arbitre : pas
aujourd'hui. Aucun nombre ne bouge dans ce lot, et un test le prouve.

⚠️ ET LE DEFAUT EST PLUS LARGE QUE LE CONSTAT NE LE DIT : mesure, A5 compare
DEJA deux bases entre ses propres modeles -- CANN applique l'offset dans son
`forward` (comptage), TabNet non (unitaire).
"""

from __future__ import annotations

import unittest

from core.conformite_reglementaire import (
    BASE_GINI_COMPTAGE,
    BASE_GINI_COUT_MOYEN,
    BASE_GINI_UNITAIRE,
    reserve_bases_gini_melangees,
)


class TestBaseGiniDeclaree(unittest.TestCase):
    """La base se declare, le melange se dit, et aucun nombre ne bouge."""

    # ══════════════════════════════════════════════════════════════════════
    # ① L'ECART EST REEL, ET IL VIENT DE L'EXPOSITION
    # ══════════════════════════════════════════════════════════════════════

    def test_les_deux_bases_ne_rendent_pas_le_meme_gini(self):
        """⚠️ Le fait qui motive tout le lot, remesure a chaque exécution.

        Second sens planté : à exposition CONSTANTE, les deux bases doivent
        coïncider — sinon l'écart viendrait d'autre chose que l'exposition et
        toute l'explication serait fausse.
        """
        import numpy as np

        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM

        a3 = AgentA3GLM(models_path='/tmp', audit_path='/tmp', verbose=False)
        rng = np.random.default_rng(11)
        n = 4000
        expo = rng.uniform(0.1, 1.0, n)
        taux = rng.gamma(2.0, 0.10, n)
        obs = rng.poisson(taux * expo)
        pred_taux = taux * rng.normal(1.0, 0.15, n)

        g_unitaire = a3._calculer_gini(obs / expo, pred_taux)
        g_comptage = a3._calculer_gini(obs, pred_taux * expo)
        self.assertGreater(
            abs(g_comptage - g_unitaire), 0.02,
            f"Les deux bases rendent le même Gini ({g_comptage:.4f} contre "
            f"{g_unitaire:.4f}) : la réserve n'aurait plus d'objet.")

        # ⚠️ SECOND SENS : sans variation d'exposition, plus d'écart.
        un = np.ones(n)
        obs_c = rng.poisson(taux)
        self.assertAlmostEqual(
            a3._calculer_gini(obs_c, taux * un),
            a3._calculer_gini(obs_c / un, taux), places=6,
            msg="À exposition constante les deux bases divergent : l'écart ne "
                "vient donc PAS de l'exposition, et l'explication publiée est "
                "fausse.")

    # ══════════════════════════════════════════════════════════════════════
    # ② CHAQUE AGENT DECLARE SA BASE, MESUREE
    # ══════════════════════════════════════════════════════════════════════

    def test_a3_declare_ses_trois_bases_distinctes(self):
        """⚠️ Contrôle par AST : les trois modèles d'A3 n'ont pas la même base.

        On relève les valeurs associées à la clé `'base_gini'` DANS LES
        DICTIONNAIRES du module — un relevé au texte confondrait la
        déclaration avec l'import ou un commentaire.
        """
        import ast
        import inspect

        from direction_non_vie.tarification.a3_glm import agent as mod

        arbre = ast.parse(inspect.getsource(mod))
        valeurs = set()
        for n in ast.walk(arbre):
            if not isinstance(n, ast.Dict):
                continue
            for cle, val in zip(n.keys, n.values):
                if (isinstance(cle, ast.Constant) and cle.value == 'base_gini'
                        and isinstance(val, ast.Name)):
                    valeurs.add(val.id)
        self.assertEqual(
            valeurs,
            {'BASE_GINI_COMPTAGE', 'BASE_GINI_COUT_MOYEN', 'BASE_GINI_UNITAIRE'},
            f"A3 ne déclare plus trois bases distinctes (relevé : {valeurs}). "
            f"Le Poisson trie sur un comptage, le Gamma sur un coût moyen et "
            f"le Tweedie sur une prédiction unitaire.")

    def test_a5_declare_DEUX_bases_entre_ses_propres_modeles(self):
        """⚠️⚠️ Trouvaille du lot : CANN applique l'offset, TabNet non."""
        import inspect

        from direction_non_vie.tarification.a5_deep_learning import agent as mod

        src = inspect.getsource(mod._AgentA5 if hasattr(mod, '_AgentA5')
                                else mod)
        self.assertIn("nom == 'cann'", src,
                      "A5 ne distingue plus la base de CANN de celle de "
                      "TabNet : elles ne sont pourtant pas les mêmes.")

    # ══════════════════════════════════════════════════════════════════════
    # ③ LE MELANGE SE DECLARE — et une base ABSENTE n'est pas assimilee
    # ══════════════════════════════════════════════════════════════════════

    def test_une_base_unique_ne_declenche_rien(self):
        """Second sens : pas de mélange, pas de réserve. Une réserve qui se
        déclenche toujours n'informe plus de rien."""
        catalogue = [{'modele': 'A', 'base_gini': BASE_GINI_UNITAIRE},
                     {'modele': 'B', 'base_gini': BASE_GINI_UNITAIRE}]
        self.assertIsNone(reserve_bases_gini_melangees(catalogue))
        self.assertIsNone(reserve_bases_gini_melangees([]))
        self.assertIsNone(reserve_bases_gini_melangees(None))

    def test_le_melange_nomme_les_modeles_de_chaque_base(self):
        catalogue = [{'modele': 'GLM_POISSON', 'base_gini': BASE_GINI_COMPTAGE},
                     {'modele': 'ML_GBM', 'base_gini': BASE_GINI_UNITAIRE},
                     {'modele': 'GLM_GAMMA', 'base_gini': BASE_GINI_COUT_MOYEN}]
        texte = reserve_bases_gini_melangees(catalogue)
        self.assertIsNotNone(texte)
        for attendu in ('GLM_POISSON', 'ML_GBM', 'GLM_GAMMA',
                        'comptage prédit', '18,1 %'):
            self.assertIn(attendu, texte)

    def test_une_base_NON_DECLAREE_est_signalee_comme_telle(self):
        """⚠️ Jamais assimilée à une autre : ne pas savoir n'est pas savoir."""
        catalogue = [{'modele': 'A', 'base_gini': BASE_GINI_UNITAIRE},
                     {'modele': 'INCONNU', 'base_gini': None}]
        texte = reserve_bases_gini_melangees(catalogue)
        self.assertIn('NON DÉCLARÉE', texte)
        self.assertIn('INCONNU', texte)

    # ══════════════════════════════════════════════════════════════════════
    # ④ AUCUN NOMBRE NE BOUGE — c'est la condition du lot
    # ══════════════════════════════════════════════════════════════════════

    def test_declarer_la_base_ne_touche_a_aucun_gini(self):
        """⚠️ `base_gini` est une CLÉ EN PLUS, jamais un calcul modifié.

        Contrôle par AST : aucune affectation de `gini`, `gini_test` ou
        `gini_train` ne doit mentionner `base_gini` — sinon la déclaration
        serait devenue un calcul.
        """
        import ast
        import inspect

        from direction_non_vie.tarification.a3_glm import agent as m3
        from direction_non_vie.tarification.a4_ml import agent as m4

        for mod, nom in ((m3, 'A3'), (m4, 'A4')):
            arbre = ast.parse(inspect.getsource(mod))
            for n in ast.walk(arbre):
                if isinstance(n, ast.Assign):
                    cibles = ast.unparse(n.targets[0])
                    if cibles.startswith(('gini', 'self.gini')):
                        self.assertNotIn(
                            'base_gini', ast.unparse(n.value),
                            f"{nom} : le calcul d'un Gini dépend désormais de "
                            f"`base_gini` — la déclaration est devenue un "
                            f"calcul, et un prix peut avoir bougé.")

    def test_la_reserve_est_publiee_dans_l_excel(self):
        import inspect

        from direction_non_vie.tarification.services import tarif_excel

        src = inspect.getsource(tarif_excel)
        self.assertIn('reserve_bases_gini', src)
        self.assertIn('Bases de Gini mélangées', src)


if __name__ == '__main__':
    unittest.main()
