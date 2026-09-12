r"""
==============================================================================
  UNE FENETRE NE PUBLIE JAMAIS LE CHIFFRE D'UNE AUTRE
==============================================================================

⚠️⚠️ CE QUE CE CONTROLE EXISTE POUR EMPECHER, ET IL EST ARRIVE. Dans le
walk-forward d'A6, `gini_train_wf` n'etait affectee qu'a l'interieur d'un
`try` IMBRIQUE, et lue hors des DEUX `try` au moment de publier la
fenetre. Quand le `try` exterieur levait avant d'atteindre ce bloc :

    a la PREMIERE fenetre   -> `UnboundLocalError`
    aux fenetres SUIVANTES  -> **la valeur de la fenetre precedente**
                               publiee comme etant celle-ci

Sa jumelle `gini_wf`, elle, etait bien initialisee avant le `try`.
*Deux variables jumelles du meme dictionnaire, deux traitements.*

⚠️⚠️ ET C'EST 30 % DU SCORE QUI DESIGNE LE MODELE DE PRODUCTION.
`gini_train_recalibre` alimente `ratio_sur_apprentissage`. Une fenetre qui
emprunte le Gini d'apprentissage d'un autre exercice fausse la mesure du
sur-apprentissage **dans le sens rassurant** : le modele parait stable
parce qu'on lui prete la stabilite d'une autre annee.

⚠️⚠️ LE CODE LE PROMETTAIT DEJA, EN TOUTES LETTRES : << La contrepartie
d'apprentissage VOYAGE avec elle >>. *Une phrase de portee n'est pas un
comportement. Celle-ci ne tenait que lorsque rien n'echouait -- c'est
exactement le cas ou elle comptait.*

CE QUE CES CONTROLES SURVEILLENT, ET CE QU'ILS NE SURVEILLENT PAS. Ils ne
cherchent pas la ligne `gini_train_wf = None`. Ils exigent le
COMPORTEMENT -- une fenetre en echec publie `None` -- et, par AST, que
AUCUN champ publie de la fenetre ne puisse porter la valeur d'un tour
precedent. *Un champ ajoute demain avec la meme asymetrie rougira sans que
personne ait a y penser.*
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

_A6 = (_RACINE / 'direction_non_vie' / 'tarification' / 'a6_comparaison'
       / 'agent.py')
_CACHE: dict = {}


def _jeu_multi_annees(n_par_annee=900, annees=(2019, 2020, 2021, 2022),
                      graine=7):
    """Un portefeuille SYNTHETIQUE pluriannuel avec du signal.

    ⚠️ Sans signal, le Gini serait degenere et les fenetres ne
    porteraient rien a comparer.
    """
    import numpy as np
    import pandas as pd
    r = np.random.default_rng(graine)
    blocs = []
    for an in annees:
        n = n_par_annee
        age = r.integers(18, 80, n).astype(float)
        bonus = r.uniform(0.5, 1.6, n)
        puiss = r.integers(4, 12, n).astype(float)
        expo = r.uniform(0.3, 1.0, n)
        lam = (0.06 + 0.004 * np.maximum(30 - age, 0)
               + 0.05 * (bonus - 0.5) + 0.006 * (puiss - 4)) * expo
        blocs.append(pd.DataFrame({
            'annee_souscription': an, 'age': age, 'bonus_malus': bonus,
            'puissance_fiscale': puiss, 'exposition': expo,
            'nb_sinistres': r.poisson(np.maximum(lam, 1e-4))}))
    return pd.concat(blocs, ignore_index=True)


def _backtest(agent=None):
    """Le walk-forward, lance une fois pour tout le fichier."""
    import logging
    import warnings

    from direction_non_vie.tarification.a6_comparaison.agent import (
        AgentA6Comparaison,
    )
    classement = [{'modele': 'GLM_POISSON', 'famille': 'GLM',
                   'gini_test': 0.20, 'rmse_test': 0.5,
                   'overfit_ratio': 1.0, 'interpretabilite': 0.9,
                   'score_global': 0.7}]
    a = agent if agent is not None else AgentA6Comparaison()
    warnings.filterwarnings('ignore')
    niveau = logging.getLogger().level
    logging.disable(logging.CRITICAL)
    try:
        return a._backtesting_temporel(
            _CACHE.setdefault('df', _jeu_multi_annees()),
            col_cible='nb_sinistres', col_expo='exposition',
            classement=classement)
    finally:
        logging.disable(niveau)


class TestLaContrepartieNeVoyagePasEntreFenetres(unittest.TestCase):

    def test_CAW1_SCEAU_une_fenetre_en_echec_publie_None_pas_la_voisine(self):
        """⚠️⚠️ LE SCEAU, ET IL PORTE SUR LE COMPORTEMENT. On fait echouer la
        recalibration d'une fenetre APRES qu'une autre a reussi. La fenetre
        en echec doit publier `None`. Si elle publie le chiffre de sa
        voisine, le defaut est revenu -- *quelle qu'en soit la cause*."""
        from direction_non_vie.tarification.a6_comparaison.agent import (
            AgentA6Comparaison,
        )
        agent = AgentA6Comparaison()
        vrai = agent._gini_lorenz
        etat = {'n': 0}

        def _gini_qui_lache(*args, **kwargs):
            #: ⚠️ on laisse passer les DEUX appels de la premiere fenetre
            #: (test puis apprentissage), puis on fait lever. L'echec tombe
            #: donc dans le `try` EXTERIEUR des fenetres suivantes, avant
            #: le bloc imbrique -- exactement le chemin du defaut.
            etat['n'] += 1
            if etat['n'] > 2:
                raise RuntimeError('recalibration indisponible')
            return vrai(*args, **kwargs)

        agent._gini_lorenz = _gini_qui_lache
        bt = _backtest(agent)
        wf = (bt or {}).get('walk_forward') or []
        self.assertGreaterEqual(
            len(wf), 2,
            f"{len(wf)} fenetre(s) : il en faut au moins deux pour qu'une "
            f"valeur puisse VOYAGER de l'une a l'autre.")

        reussies = [f for f in wf if f.get('gini_recalibre') is not None]
        echouees = [f for f in wf if f.get('gini_recalibre') is None]
        self.assertTrue(
            reussies and echouees,
            f"l'injection n'a pas produit le cas cherche : "
            f"{len(reussies)} reussie(s), {len(echouees)} echouee(s). "
            f"Ce controle ne peut rien attester d'un scenario absent.")

        #: ⚠️⚠️ LE COEUR. Une fenetre sans Gini de test ne peut pas avoir
        #: un Gini d'apprentissage : le calcul de l'un precede l'autre dans
        #: le meme bloc. S'il y en a un, il vient d'ailleurs.
        for f in echouees:
            self.assertIsNone(
                f.get('gini_train_recalibre'),
                f"fenetre {f.get('annee_test')} : `gini_recalibre` est None "
                f"mais `gini_train_recalibre` vaut "
                f"{f.get('gini_train_recalibre')} -- cette valeur ne peut "
                f"venir que d'une AUTRE fenetre.")

        #: ⚠️ et la preuve que la valeur EXISTAIT bien pour voyager
        valeurs = [f.get('gini_train_recalibre') for f in reussies]
        self.assertTrue(
            any(v is not None for v in valeurs),
            "aucune fenetre n'a produit de contrepartie : rien ne pouvait "
            "voyager, donc ce controle ne prouve rien.")
        print(f"    CAW-1 SCEAU : {len(reussies)} fenetre(s) reussie(s) "
              f"(train={valeurs}), {len(echouees)} en echec publient None")

    def test_CAW2_SCEAU_aucun_champ_publie_ne_peut_survivre_a_son_tour(self):
        """⚠️⚠️ LA CLASSE, PAS L'EXEMPLAIRE. Par AST : tout nom local publie
        dans l'enregistrement de fenetre doit avoir une affectation
        INCONDITIONNELLE dans la boucle. Sans elle, une fenetre peut porter
        la valeur de la precedente. *Un champ ajoute demain avec la meme
        asymetrie rougit ici sans que personne y pense.*"""
        arbre = ast.parse(_A6.read_bytes().decode('utf-8'))
        fn = next((n for n in ast.walk(arbre)
                   if isinstance(n, ast.FunctionDef)
                   and n.name == '_backtesting_temporel'), None)
        self.assertIsNotNone(
            fn, "`_backtesting_temporel` est introuvable : ce controle "
                "surveillerait le vide.")

        gardes = []
        for n in ast.walk(fn):
            if isinstance(n, (ast.Try, ast.ExceptHandler, ast.If,
                              ast.While, ast.With)):
                gardes.append((n.lineno, max(
                    (getattr(d, 'lineno', 0) for d in ast.walk(n)),
                    default=n.lineno)))

        def sous_garde(lg):
            return any(a <= lg <= b for a, b in gardes)

        #: l'enregistrement publie : le `dict` passe a `walk_forward.append`
        publie = None
        for n in ast.walk(fn):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'append'
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == 'walk_forward'
                    and n.args and isinstance(n.args[0], ast.Dict)):
                publie = n.args[0]
        self.assertIsNotNone(
            publie, "l'enregistrement de fenetre n'est plus un `dict` "
                    "litteral passe a `walk_forward.append` : ce controle "
                    "ne sait plus ou regarder, et doit etre relu.")

        ecrit: dict = {}
        for n in ast.walk(fn):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                ecrit.setdefault(n.id, []).append(n.lineno)

        params = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
        fautifs = []
        for v in publie.values:
            for nd in ast.walk(v):
                if not isinstance(nd, ast.Name) or not isinstance(
                        nd.ctx, ast.Load):
                    continue
                nom = nd.id
                if nom in params or nom not in ecrit:
                    continue
                if not any(not sous_garde(lg) for lg in ecrit[nom]):
                    fautifs.append((nom, sorted(set(ecrit[nom]))))

        self.assertEqual(
            sorted(set(fautifs)), [],
            f"champ(s) de fenetre sans affectation inconditionnelle : "
            f"{sorted(set(fautifs))}. Chacun peut publier la valeur du tour "
            f"precedent quand son bloc ne s'execute pas.")
        print(f"    CAW-2 SCEAU : {len(publie.keys)} champs publies, "
              f"0 sans affectation inconditionnelle")

    def test_CAW3_CONTRE_EPREUVE_un_walk_forward_SAIN_ne_bouge_pas(self):
        """⚠️ Le second sens, et il est indispensable : un correctif qui
        viderait aussi les fenetres SAINES aurait remplace un defaut par une
        perte de mesure. *Un controle qui ne verifie qu'un sens accuse.*"""
        bt = _CACHE.setdefault('sain', _backtest())
        wf = (bt or {}).get('walk_forward') or []
        self.assertTrue(wf, 'aucune fenetre produite')
        avec = [f for f in wf
                if f.get('gini_train_recalibre') is not None]
        self.assertTrue(
            avec,
            f"sur {len(wf)} fenetres saines, AUCUNE ne publie de "
            f"contrepartie d'apprentissage : la mesure a disparu au lieu "
            f"d'etre reparee.")
        #: ⚠️ et les valeurs sont DISTINCTES d'une fenetre a l'autre --
        #: deux fenetres portant le meme chiffre seraient le symptome meme
        #: du defaut, cette fois sans echec pour l'expliquer.
        vals = [f['gini_train_recalibre'] for f in avec]
        if len(vals) > 1:
            self.assertEqual(
                len(set(vals)), len(vals),
                f"deux fenetres saines publient la MEME contrepartie "
                f"{vals} : une valeur voyage encore.")
        print(f"    CAW-3 contre-epreuve : {len(avec)}/{len(wf)} fenetres "
              f"saines publient une contrepartie, toutes distinctes")


if __name__ == '__main__':
    unittest.main(verbosity=2)
