"""Contrôles positifs — constat `a3/C6` : le Tweedie pose enfin son Gini.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
Avant ce lot, `_calibrer_tweedie` ne publiait **aucun** Gini. A6 le lisait par
`met.get('gini', 0)` : le modèle entrait donc dans l'arbitrage **noté zéro par
un littéral que personne n'avait mesuré**. Mesuré depuis : le vrai Gini du
Tweedie vaut **-0,078** — négatif. *Le zéro fabriqué était flatteur.*

Trois propriétés sont contrôlées ici, chacune avec **sa violation plantée** :

  ① le Gini du Tweedie est **calculé**, jamais littéral ;
  ② un Gini **non mesurable** se publie `None`, **jamais `0`** — un zéro est
    indiscernable d'un pouvoir discriminant nul ;
  ③ A6 **écarte en le déclarant** un modèle au Gini non mesuré, et **déclare**
    un arbitrage à candidat unique.

⚠️ Le second sens de chaque contrôle est testé : il doit **échouer** quand la
propriété est violée, pas seulement passer quand elle tient.

⚠️⚠️ CES TESTS SONT DES `unittest.TestCase`, ET CE N'EST PAS UN DÉTAIL DE
STYLE. La gate exécute `unittest`, qui **ne collecte PAS** les fonctions
`test_*` au niveau module. Écrites en style pytest, elles passaient sous ce
dernier et la gate sortait en 0 **sans les avoir exécutées** : le silence
aurait ressemblé au succès. Un garde-fou de `core` l'a planté.
"""

from __future__ import annotations

import unittest

import numpy as np

from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison


def _a6() -> AgentA6Comparaison:
    return AgentA6Comparaison(models_path='/tmp', audit_path='/tmp', verbose=False)


def _resultat_a3(gini_tweedie, *, cible: str = 'prime_pure') -> dict:
    """Un retour d'A3 minimal, réduit à ce que `_agreger_resultats` lit."""
    return {
        'success': True,
        'metriques': {
            'tweedie': {
                'cible': cible,
                'gini': gini_tweedie,
                'rmse_test': 12.0,
                'nb_vars_retenues': 4,
                'aic': 100.0,
                'bic': 110.0,
            }
        },
    }


# ══════════════════════════════════════════════════════════════════════════
# ① LE GINI DU TWEEDIE EST CALCULÉ, PAS LITTÉRAL
# ══════════════════════════════════════════════════════════════════════════

class TestGiniTweedieArbitrage(unittest.TestCase):
    """Le Gini du Tweedie, et la reserve d'arbitrage a candidat unique."""

    def test_le_tweedie_publie_un_gini_calcule_pas_un_litteral(self):
        """`_calibrer_tweedie` doit APPELER `_calculer_gini`, pas poser un nombre.

        ⚠️ Contrôle par AST, jamais par `grep` : on exige que l'appel existe
        **dans le corps de la méthode**, ce qu'un relevé au texte confondrait avec
        une mention en commentaire ou dans une autre méthode du même fichier.
        """
        import ast
        import inspect

        from direction_non_vie.tarification.a3_glm import agent as mod_a3

        src = inspect.getsource(mod_a3.AgentA3GLM._calibrer_tweedie)
        arbre = ast.parse(src.lstrip())
        appels = [
            n for n in ast.walk(arbre)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == '_calculer_gini'
        ]
        assert appels, (
            "Le Tweedie ne calcule plus son Gini : A6 le noterait zéro par "
            "`met.get('gini', 0)`, et il entrerait dans l'arbitrage avec une note "
            "que personne n'a mesurée.")

    def test_le_gini_du_tweedie_est_bien_celui_du_couple_observe_predit(self):
        """Le Gini publié doit être celui de (prime pure observée, prédite).

        On rejoue `_calculer_gini` sur un couple connu et on vérifie qu'il
        discrimine — le second sens : un vecteur prédit CONSTANT ne discrimine
        rien, et le Gini doit alors s'effondrer vers zéro.
        """
        from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM

        a3 = AgentA3GLM(models_path='/tmp', audit_path='/tmp', verbose=False)
        rng = np.random.default_rng(0)
        obs = rng.gamma(2.0, 150.0, 500)

        gini_informatif = a3._calculer_gini(obs, obs)          # prédiction parfaite
        gini_constant = a3._calculer_gini(obs, np.ones(500))   # ne discrimine rien

        assert gini_informatif > 0.2, (
            f"Une prédiction parfaite doit fortement discriminer "
            f"(obtenu {gini_informatif:.4f}).")
        # ⚠️ LA VIOLATION PLANTÉE : si `_calculer_gini` rendait une constante,
        # les deux valeurs seraient égales et le Gini ne mesurerait rien.
        assert abs(gini_constant) < abs(gini_informatif), (
            f"Une prédiction constante obtient {gini_constant:.4f} contre "
            f"{gini_informatif:.4f} pour une prédiction parfaite : le Gini publié "
            f"ne dépend pas des prédictions, il ne mesure donc rien.")


    # ══════════════════════════════════════════════════════════════════════════
    # ② UN GINI NON MESURABLE VAUT `None`, JAMAIS `0`
    # ══════════════════════════════════════════════════════════════════════════

    def test_un_gini_non_mesurable_ne_se_publie_jamais_zero(self):
        """⚠️ Un zéro est indiscernable d'un pouvoir discriminant nul.

        On teste la propriété qui compte pour l'actuaire : `0` et « non mesuré »
        doivent produire **deux comportements différents** chez A6.
        """
        catalogue_zero, _, exc_zero = _a6()._agreger_resultats(
            _resultat_a3(0.0), None, None, col_cible='prime_pure')
        assert len(catalogue_zero) == 1 and not exc_zero, (
            "Un Gini de 0,0 est une valeur MESURÉE : le modèle reste candidat.")

        with self.assertRaisesRegex(ValueError, "Gini non mesuré"):
            _a6()._agreger_resultats(
                _resultat_a3(None), None, None, col_cible='prime_pure')

    def test_le_gini_non_mesure_est_ecarte_en_le_declarant(self):
        """Écarter en silence serait le même défaut que noter zéro en silence."""
        a3_ok = _resultat_a3(0.21)
        a3_ok['metriques']['poisson'] = {
            'cible': 'prime_pure', 'gini': None, 'rmse_test': 9.0,
            'nb_vars_retenues': 3, 'aic': 90.0, 'bic': 95.0}

        catalogue, _, exclusions = _a6()._agreger_resultats(
            a3_ok, None, None, col_cible='prime_pure')

        assert [m['modele'] for m in catalogue] == ['GLM_TWEEDIE']
        assert len(exclusions) == 1, (
            "Le modèle au Gini non mesuré a disparu SANS être déclaré : un écart "
            "silencieux est aussi grave que la note fabriquée qu'il remplace.")
        assert exclusions[0]['modele'] == 'GLM_POISSON'
        assert exclusions[0]['metrique'] == 'gini_test'
        assert 'fabriquée' in exclusions[0]['raison']

    def test_le_filtre_protege_le_score_multicriteres_d_un_typeerror(self):
        """⚠️ Second sens : sans le filtre, la notation LÈVE — la page tomberait.

        `_calculer_scores_multicriteres` divise par `max(ginis)`. On plante la
        violation en lui passant directement un catalogue non filtré : il doit
        échouer, ce qui prouve que le filtre en amont n'est pas décoratif.
        """
        catalogue_pollue = [
            {'modele': 'X', 'famille': 'GLM', 'gini_test': None,
             'rmse_test': 1.0, 'overfit_ratio': 1.0, 'nb_vars': 2},
        ]
        with self.assertRaises(TypeError):
            _a6()._calculer_scores_multicriteres(
                catalogue_pollue,
                {'gini': 0.4, 'stabilite': 0.3, 'interpretabilite': 0.2,
                 'rmse': 0.1})


    # ══════════════════════════════════════════════════════════════════════════
    # ③ UN ARBITRAGE ENTRE UN SEUL CANDIDAT N'EST PAS UN ARBITRAGE
    # ══════════════════════════════════════════════════════════════════════════

    def test_le_catalogue_a_un_seul_candidat_est_bien_le_cas_reel(self):
        """Mesuré : sur `prime_pure`, A3 seul ne propose QUE le Tweedie.

        Ce test fige le fait qui motive la réserve — le Poisson vise la fréquence
        et le Gamma le coût moyen, donc le filtre par cible les écarte.
        """
        a3 = _resultat_a3(0.13)
        a3['metriques']['poisson'] = {
            'cible': 'nb_sinistres', 'gini': 0.09, 'rmse_test': 1.0,
            'nb_vars_retenues': 3, 'aic': 1.0, 'bic': 1.0}
        a3['metriques']['gamma'] = {
            'cible': 'cout_moyen', 'gini': 0.01, 'rmse_test': 1.0,
            'nb_vars_retenues': 3, 'aic': 1.0, 'bic': 1.0}

        catalogue, exclusions_cible, _ = _a6()._agreger_resultats(
            a3, None, None, col_cible='prime_pure')

        assert [m['modele'] for m in catalogue] == ['GLM_TWEEDIE'], (
            "Le catalogue sur `prime_pure` ne contient plus le seul Tweedie : la "
            "réserve d'arbitrage à candidat unique doit être revue avec lui.")
        assert len(exclusions_cible) == 2

    def test_la_reserve_d_arbitrage_est_un_champ_du_retour_pas_un_log(self):
        """⚠️ Une réserve qui ne vit que dans un log n'atteint aucun actuaire.

        Contrôle par AST : `run()` doit ÉCRIRE `reserve_arbitrage` dans son
        rapport, et le retour d'A6 doit porter la clé — sinon la réserve resterait
        invisible, exactement le défaut de `conformite/C7`.
        """
        import ast
        import inspect

        from direction_non_vie.tarification.a6_comparaison import agent as mod_a6

        src = inspect.getsource(mod_a6.AgentA6Comparaison.run)
        arbre = ast.parse(src.lstrip())

        ecrit_rapport = any(
            isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Subscript)
                    and isinstance(t.slice, ast.Constant)
                    and t.slice.value == 'reserve_arbitrage'
                    for t in n.targets)
            for n in ast.walk(arbre))
        assert ecrit_rapport, "`run()` n'écrit plus la réserve dans son rapport."

        porte_la_cle = any(
            isinstance(n, ast.Constant) and n.value == 'reserve_arbitrage'
            for n in ast.walk(arbre))
        assert porte_la_cle, (
            "Le retour d'A6 ne porte plus `reserve_arbitrage` : la réserve "
            "n'atteindrait plus l'Excel, donc plus l'actuaire.")

    def test_la_reserve_est_publiee_dans_l_excel(self):
        """Le dernier maillon : l'Excel doit contenir la phrase de réserve.

        ⚠️ Relevé au TEXTE du module d'export, résolu vers un chemin de fichier
        réel — pas une supposition sur un nom de fonction.
        """
        import inspect

        from direction_non_vie.tarification.services import tarif_excel

        src = inspect.getsource(tarif_excel)
        assert "reserve_arb" in src, (
            "L'export Excel ne lit plus la réserve d'arbitrage : elle serait "
            "calculée, transportée... et jamais lue.")
        assert "Réserve sur l'arbitrage" in src


if __name__ == '__main__':
    unittest.main()
