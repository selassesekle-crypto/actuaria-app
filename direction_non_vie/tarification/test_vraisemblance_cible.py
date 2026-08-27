"""Controles positifs — constat `a6/C8` : le plafond de vraisemblance et la cible.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
`gini_est_plausible(gini, cible_est_frequence=True)` etait appele avec `True`
CODE EN DUR, alors que la cible peut valoir `cout_moyen` ou `prime_pure`. Les
deux corrections evidentes etaient fausses, et c'est MESURE :

  · passer la vraie cible -> l'ancienne fonction rendait `True` SANS PLAFOND
    pour toute cible non-frequence. Mesure : 0,91 et 0,99 passaient alors sans
    une alerte -- sur `prime_pure`, LA CIBLE MEME de la fuite historique V8
    qui a motive ce garde-fou ;
  · laisser `True` -> on applique a une prime pure un seuil calibre sur une
    frequence.

⚠️⚠️ LA SORTIE : le garde-fou DECLARE qu'il ne sait pas juger, au lieu de
repondre « plausible ». Trois etats, pas deux.

⚠️ ET LE NOM A CHANGE EXPRES. Un retour a trois etats sous le nom
`gini_est_plausible` aurait ete SILENCIEUSEMENT faux : tout appelant ecrivait
`if not gini_est_plausible(...)`, et `NON_CALIBRE` est une chaine vraie --
l'alerte n'aurait plus jamais tire. En renommant, un appelant reste en arriere
echoue BRUYAMMENT.

⚠️ Ces tests sont des `unittest.TestCase` : la gate execute `unittest`.
"""

from __future__ import annotations

import unittest

from core.conformite_reglementaire import (
    GINI_PLAUSIBLE_MAX_FREQUENCE,
    VRAISEMBLANCE_IMPLAUSIBLE,
    VRAISEMBLANCE_NON_CALIBRE,
    VRAISEMBLANCE_PLAUSIBLE,
    VRAISEMBLANCE_SANS_OBJET,
    reserve_vraisemblance_non_calibree,
    verdict_vraisemblance_gini,
)
from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison


def _a6() -> AgentA6Comparaison:
    return AgentA6Comparaison(models_path='/tmp', audit_path='/tmp', verbose=False)


def _backtest_impeccable() -> dict:
    return {'walk_forward': {'n_fenetres': 3, 'ae_moyen': 1.0, 'stabilite': 'OK',
                             'modele': 'GLM_POISSON',
                             'methode': 'walk_forward_temporel_avec_recalibration'}}


def _modele(cible: str, gini: float = 0.31) -> dict:
    return {'modele': 'GLM_POISSON', 'famille': 'GLM', 'cible': cible,
            'gini_test': gini, 'gini_train': gini + 0.02, 'score_global': 0.72,
            'rmse_test': 1.0, 'overfit_ratio': 1.02, 'nb_vars': 5,
            'interpretabilite': 1.0}


class TestVraisemblanceCible(unittest.TestCase):
    """Trois etats, la cible mesuree, et l'absence de controle qui se publie."""

    # ══════════════════════════════════════════════════════════════════════
    # ① TROIS ETATS, PAS DEUX
    # ══════════════════════════════════════════════════════════════════════

    def test_les_trois_etats_sont_distincts(self):
        """⚠️ « je ne sais pas juger » n'est ni plausible ni implausible."""
        self.assertEqual(
            verdict_vraisemblance_gini(0.20, cible_est_frequence=True),
            VRAISEMBLANCE_PLAUSIBLE)
        self.assertEqual(
            verdict_vraisemblance_gini(0.91, cible_est_frequence=True),
            VRAISEMBLANCE_IMPLAUSIBLE)
        self.assertEqual(
            verdict_vraisemblance_gini(0.91, cible_est_frequence=False),
            VRAISEMBLANCE_NON_CALIBRE)
        self.assertEqual(
            verdict_vraisemblance_gini(None, cible_est_frequence=False),
            VRAISEMBLANCE_SANS_OBJET)

    def test_la_fuite_historique_ne_passe_plus_en_silence(self):
        """⚠️⚠️ LE TEST QUI MOTIVE TOUT LE LOT.

        Le correctif « evident » (passer la vraie cible a l'ancienne fonction
        booleenne) rendait `True` pour 0,91 sur `prime_pure` -- la cible meme
        de la fuite V8. Ici, ce Gini ne peut plus etre declare plausible.
        """
        for gini in (0.91, 0.92, 0.99):
            verdict = verdict_vraisemblance_gini(gini, cible_est_frequence=False)
            self.assertNotEqual(
                verdict, VRAISEMBLANCE_PLAUSIBLE,
                f"Gini={gini} sur une cible non-fréquence est déclaré "
                f"PLAUSIBLE : c'est exactement ce que faisait l'ancienne "
                f"fonction, et c'est la valeur des deux fuites historiques.")
            self.assertEqual(verdict, VRAISEMBLANCE_NON_CALIBRE)

    def test_l_ancien_nom_a_disparu(self):
        """⚠️ SECOND SENS — un appelant reste en arriere doit echouer FORT.

        `gini_est_plausible` etait un predicat ; le garder avec un retour a
        trois etats aurait rendu `if not ...` toujours faux, donc l'alerte
        muette. Sa disparition rend l'erreur bruyante.
        """
        import core.conformite_reglementaire as mod
        self.assertFalse(
            hasattr(mod, 'gini_est_plausible'),
            "`gini_est_plausible` est revenu : un appelant peut de nouveau "
            "écrire `if not gini_est_plausible(...)` et perdre l'alerte en "
            "silence.")

    # ══════════════════════════════════════════════════════════════════════
    # ② LE STATUT : une absence de controle n'est pas un controle satisfait
    # ══════════════════════════════════════════════════════════════════════

    def test_la_frequence_garde_son_vert(self):
        """Le correctif ne doit RIEN changer sur la cible ou le plafond vaut."""
        statut = _a6()._calculer_statut_rag(
            _modele('nb_sinistres'), [_modele('nb_sinistres')],
            profil_valide_par='Actuaire Test', environnement='etude',
            backtest=_backtest_impeccable(), cible_est_frequence=True)
        self.assertEqual(statut, 'VERT')

    def test_une_cible_non_calibree_bloque_le_vert_en_le_disant(self):
        """⚠️⚠️ Le VERT affirme que TOUT a ete verifie.

        Si le plafond ne sait pas juger, il bloque le VERT -- exactement comme
        le fait deja `_backtest_ok` quand la validation temporelle est
        indisponible. ⚠️ Ce n'est PAS une mise hors service : AMBRE, pas ROUGE.
        """
        statut = _a6()._calculer_statut_rag(
            _modele('prime_pure'), [_modele('prime_pure')],
            profil_valide_par='Actuaire Test', environnement='etude',
            backtest=_backtest_impeccable(), cible_est_frequence=False)
        self.assertEqual(
            statut, 'AMBRE',
            "Une cible dont le plafond n'est pas calibré doit plafonner à "
            "AMBRE — ni VERT (le contrôle n'a pas eu lieu), ni ROUGE (rien "
            "n'établit un défaut).")

    def test_le_defaut_de_la_methode_preserve_les_invariants(self):
        """⚠️ `cible_est_frequence` vaut `True` par defaut, et c'est VOULU.

        Une quarantaine de sites de test appellent `_calculer_statut_rag` sans
        cet argument -- dont les invariants de FUITE. Ils doivent continuer a
        prouver EXACTEMENT ce qu'ils prouvaient.
        """
        import inspect
        sig = inspect.signature(AgentA6Comparaison._calculer_statut_rag)
        self.assertIs(sig.parameters['cible_est_frequence'].default, True)

    # ══════════════════════════════════════════════════════════════════════
    # ③ LA RESERVE VOYAGE — sinon l'absence de controle est invisible
    # ══════════════════════════════════════════════════════════════════════

    def test_la_reserve_nomme_la_cible_et_le_seuil(self):
        texte = reserve_vraisemblance_non_calibree('prime_pure', 0.42)
        self.assertIn('prime_pure', texte)
        self.assertIn(str(GINI_PLAUSIBLE_MAX_FREQUENCE), texte)
        self.assertIn("n'a donc PAS été exercé", texte)

    def test_la_reserve_est_sans_objet_si_rien_a_declarer(self):
        """Second sens : pas de Gini, pas de reserve — on n'invente pas une
        alerte la ou il n'y a rien a juger."""
        self.assertIsNone(reserve_vraisemblance_non_calibree('prime_pure', None))
        self.assertIsNone(reserve_vraisemblance_non_calibree(None, 0.42))

    def test_run_passe_la_cible_MESUREE_pas_un_litteral(self):
        """⚠️ Contrôle par AST : `run()` doit dériver `cible_est_frequence` du
        PLAN, jamais le poser en dur — c'était tout le défaut de `a6/C8`."""
        import ast
        import inspect

        from direction_non_vie.tarification.a6_comparaison import agent as mod

        src = inspect.getsource(mod.AgentA6Comparaison.run)
        arbre = ast.parse(src.lstrip())
        litteral = [
            n for n in ast.walk(arbre)
            if isinstance(n, ast.keyword) and n.arg == 'cible_est_frequence'
            and isinstance(n.value, ast.Constant)
        ]
        self.assertEqual(
            litteral, [],
            "`run()` passe de nouveau `cible_est_frequence` en dur : la cible "
            "serait re-fabriquée au lieu d'être mesurée sur le plan.")
        self.assertIn('cible_frequence', src,
                      "`run()` ne lit plus `plan.cible_frequence` : seule "
                      "cette source dit ce qu'est une cible de fréquence.")

    def test_la_reserve_est_publiee_dans_l_excel(self):
        """Le dernier maillon : une réserve que personne ne lit n'existe pas."""
        import inspect

        from direction_non_vie.tarification.services import tarif_excel

        src = inspect.getsource(tarif_excel)
        self.assertIn('reserve_vraisemblance', src)
        self.assertIn("Réserve sur la vraisemblance", src)


if __name__ == '__main__':
    unittest.main()
