"""Controles positifs — constat `a6/C6` : la chaine qui ne matchait jamais.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
TROIS sites comparaient `backtest['split']` au litteral
`'walk_forward_temporel'`. Or le code n'ecrit JAMAIS cette chaine : il ecrit
`'aleatoire_80_20'` ou `'walk_forward_temporel_avec_recalibration'`.

Les trois branches etaient donc MORTES :
  · deux GARDES de test (ST4, ST5) -- les assertions ne s'executaient jamais,
    et la gate etait verte. *Le silence ressemblait au succes* ;
  · dans l'AGENT, le bloc qui publie les fenetres du walk-forward.

⚠️⚠️ CE QUE LA BRANCHE REVEILLEE A REVELE. Avant ce lot, le commentaire
actuaire publiait « A/E ratio 0,3574 » et « Deviation majeure », rien d'autre.
Mesure apres : « Fenetres WF : 3 (3 ROUGE) · Stabilite WF : Instable · CV A/E
WF : 0,1885 ». **Les TROIS fenetres etaient rouges et le modele instable, et
rien ne le disait a l'actuaire** -- alors que ce sont exactement les grandeurs
sur lesquelles le verrou du statut plafonne.

⚠️ ET REVEILLER UNE BRANCHE MORTE PEUT CASSER. Celle-ci formatait
`backtest.get('ae_cv_wf', 'N/A'):.4f`. La cle EXISTE et vaut `None` quand le
CV n'a pas pu etre calcule : le defaut du `get` ne tire pas, et `:.4f` sur
`None` LEVE. C'est la troisieme fois que « present mais VIDE » revient dans
cet audit -- corrige avant la mise en service de la branche.

⚠️ Le correctif de fond n'est pas de recopier la bonne chaine : c'est de la
NOMMER une fois. Une chaine recopiee dans quatre fichiers finit par diverger ;
une constante importee ne le peut pas.
"""

from __future__ import annotations

import ast
import inspect
import re
import unicodedata
import unittest

from direction_non_vie.tarification.a6_comparaison.agent import (
    SPLIT_ALEATOIRE,
    SPLIT_WALK_FORWARD,
    AgentA6Comparaison,
)


def _source_agent() -> str:
    from direction_non_vie.tarification.a6_comparaison import agent as mod
    return unicodedata.normalize('NFC', inspect.getsource(mod))


def _backtest(cv=0.1885, split=SPLIT_WALK_FORWARD) -> dict:
    return {'disponible': True, 'split': split, 'ae_ratio': 0.3574,
            'interpretation': '🔴 Déviation majeure', 'n_fenetres': 3,
            'n_fenetres_rouge': 3, 'stabilite_wf': '🔴 Instable',
            'ae_cv_wf': cv, 'ae_par_segment': {'zones': 1.0}}


def _modele() -> dict:
    return {'modele': 'GLM_POISSON', 'famille': 'GLM', 'cible': 'nb_sinistres',
            'gini_test': 0.31, 'gini_train': 0.33, 'score_global': 0.72,
            'rmse_test': 1.0, 'overfit_ratio': 1.02, 'nb_vars': 5,
            'interpretabilite': 1.0}


def _commentaire(bt: dict) -> str:
    a6 = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp', verbose=False)
    return a6._commenter_actuaire_senior(
        [_modele()], _modele(), 'auto', 'AMBRE', bt)


class TestSplitWalkForward(unittest.TestCase):
    """La chaine est nommee, la branche vit, et l'absence se dit."""

    # ══════════════════════════════════════════════════════════════════════
    # ① PLUS AUCUN LITTERAL COURT NE SUBSISTE
    # ══════════════════════════════════════════════════════════════════════

    def test_le_litteral_qui_ne_matchait_jamais_a_disparu(self):
        """⚠️ La forme exacte du défaut, épinglée dans l'agent ET les tests."""
        from direction_non_vie.tarification.a6_comparaison import (
            test_a6_comparaison as mod_test,
        )

        for src, ou in ((_source_agent(), 'agent'),
                        (unicodedata.normalize('NFC',
                                               inspect.getsource(mod_test)),
                         'test_a6_comparaison')):
            orphelins = re.findall(
                r"==\s*'walk_forward_temporel'", src)
            self.assertEqual(
                orphelins, [],
                f"{ou} : une comparaison au littéral court est revenue. Le "
                f"code n'écrit jamais cette chaîne — la branche serait morte "
                f"et la gate resterait verte.")

    def test_les_deux_valeurs_ecrites_sont_les_constantes(self):
        """⚠️ Contrôle par AST : `backtest['split']` ne reçoit que les
        constantes — sinon une troisième valeur pourrait réapparaître."""
        arbre = ast.parse(_source_agent())
        litteraux = []
        for n in ast.walk(arbre):
            cible = None
            if isinstance(n, ast.Assign) and n.targets:
                cible = ast.unparse(n.targets[0])
            if (cible and cible.endswith("['split']")
                    and isinstance(n.value, ast.Constant)):
                litteraux.append(f"ligne {n.lineno}: {n.value.value!r}")
        self.assertEqual(
            litteraux, [],
            f"`split` reçoit un littéral au lieu d'une constante : {litteraux}")
        self.assertNotEqual(SPLIT_ALEATOIRE, SPLIT_WALK_FORWARD)

    # ══════════════════════════════════════════════════════════════════════
    # ② LA BRANCHE VIT — et publie ce qu'elle promettait
    # ══════════════════════════════════════════════════════════════════════

    def test_le_commentaire_publie_enfin_les_fenetres(self):
        """⚠️⚠️ Avant ce lot, l'actuaire ne lisait que l'A/E."""
        texte = _commentaire(_backtest())
        for attendu in ('Fenêtres WF', '3 (3 ROUGE)', 'Stabilité WF',
                        '🔴 Instable', 'CV A/E WF', '0.1885'):
            self.assertIn(
                attendu, texte,
                f"« {attendu} » n'atteint plus le commentaire actuaire : "
                f"c'est pourtant une des grandeurs sur lesquelles le verrou "
                f"du statut plafonne.")

    def test_un_split_aleatoire_ne_publie_PAS_de_fenetres(self):
        """⚠️ Second sens : la branche ne doit pas s'ouvrir hors walk-forward.

        Sans cette assertion, un garde toujours vrai passerait pour un garde
        corrigé — on aurait remplacé une branche morte par une branche folle.
        """
        texte = _commentaire(_backtest(split=SPLIT_ALEATOIRE))
        self.assertNotIn('Fenêtres WF', texte)
        self.assertIn('A/E ratio', texte)

    # ══════════════════════════════════════════════════════════════════════
    # ③ « PRESENT MAIS VIDE » — reveiller la branche ne doit pas casser
    # ══════════════════════════════════════════════════════════════════════

    def test_un_cv_non_mesure_se_DIT_et_ne_leve_pas(self):
        """⚠️⚠️ `get('ae_cv_wf', 'N/A')` NE PROTÈGE PAS : la clé EXISTE et vaut
        `None`. Le défaut du `get` ne tire jamais, et `:.4f` sur `None` lève.

        Ce test est la raison pour laquelle la branche pouvait rester morte
        sans que personne le voie : la réveiller telle quelle aurait planté.
        """
        texte = _commentaire(_backtest(cv=None))   # ne doit PAS lever
        self.assertIn('CV A/E WF', texte)
        self.assertIn('non mesuré', texte)
        self.assertNotIn('None', texte)

    def test_un_cv_mesure_reste_formate(self):
        """Second sens : un nombre présent s'affiche toujours en clair."""
        texte = _commentaire(_backtest(cv=0.4211))
        self.assertIn('0.4211', texte)
        self.assertNotIn('non mesuré', texte)


if __name__ == '__main__':
    unittest.main()
