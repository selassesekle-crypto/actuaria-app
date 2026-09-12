r"""
==============================================================================
  UNE PREDICTION QUI ECHOUE N'EST PAS UNE PREDICTION CONSTANTE
==============================================================================

⚠️⚠️ LA CLASSE. Quand `predict` refuse, remplacer sa sortie par une MOYENNE
produit un tarif PLAT -- un prix unique pour tout le portefeuille, aucune
segmentation -- et le Gini, la RMSE et le ratio de sur-apprentissage sont
alors mesures sur une CONSTANTE, puis publies comme des mesures du modele.
La seule trace etait un `logger.warning`.

  Mesure du 13/09/2026 sur cet arbre, portefeuille synthetique, en faisant
  lever le `predict` du modele de frequence :

      frequence_annuelle   3 605 valeurs distinctes  ->  UNE seule
      charge attendue           380,68 sinistres     ->  175,00  (-54,0 %)
      exception levee                                    AUCUNE

  Le deuxieme auditeur l'avait chiffre sur son propre jeu : prime pure
  totale 293 874,25 EUR -> 117 600,00 EUR, **-60,0 %**. Deux jeux, deux
  chiffres, un seul defaut.

⚠️⚠️ LA REGLE EST CELLE QUE CE MODULE SUIVAIT DEJA, DEUX FOIS :
`_calculer_gini` rend `None` plutot qu'un zero (`a3/C6`) et
`_calibration_impossible` LEVE quand aucun modele n'est ajustable.

    sur les METRIQUES  une prediction impossible rend des metriques `None`,
                       et le MOTIF voyage avec elles ;
    sur le PRIX        on LEVE -- une prime fabriquee est le seul cas que
                       ce depot refuse partout ailleurs.

⚠️ CE CONTROLE SURVEILLE LA CLASSE, PAS LES CINQ SITES D'HIER. Son assiette
est le perimetre de production entier : un `except` neuf, dans n'importe
quel agent, qui remplacerait une prediction par une constante, le fait
rougir.

⚠️⚠️ ET SA LIMITE EST DECLAREE. Le relevé de `PI-2` lit la FORME du code ;
`PI-3` mesure le COMPORTEMENT, mais sur le chemin du PRIX seulement -- le
portefeuille synthetique de ce fichier n'atteint pas les sites de
METRIQUES (mesure : les plants y restent invisibles faute de sinistres
suffisants en test). *Le comportement du chemin metrique n'est donc pas
demontre ici ; il est tenu par la forme.* Dit plutot que taire.
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import subprocess
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))


def _fichiers_de_production() -> list[str]:
    """Ce que git publie, hors tests -- l'assiette de la classe."""
    try:
        sortie = subprocess.run(
            ['git', 'ls-files'], cwd=str(_RACINE), capture_output=True,
            text=True, encoding='utf-8', errors='replace', timeout=120,
            check=False).stdout
        rels = [f for f in sortie.split('\n') if f.endswith('.py')
                and not f.split('/')[-1].startswith('test_')]
        if rels:
            return [f for f in rels if (_RACINE / f).is_file()]
    except (OSError, subprocess.SubprocessError):
        pass
    return [str(p.relative_to(_RACINE)).replace('\\', '/')
            for p in _RACINE.rglob('*.py')
            if p.is_file() and not p.name.startswith('test_')
            and '.git' not in p.parts]


def _replis_constants(arbre: ast.AST) -> list[tuple]:
    """(ligne, code) pour chaque `except` qui remplace un `predict`.

    ⚠️ LE CRITERE EST LA CONSTANTE, PAS LE `except`. Un `except` qui
    journalise, qui leve, ou qui pose `None` ne fabrique rien -- c'est
    poser une VALEUR uniforme a la place d'une prediction qui est le
    defaut. `np.full(...)` et `.mean()` en sont les deux formes vues.
    """
    out = []
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Try) or not n.body:
            continue
        if '.predict(' not in ast.unparse(n.body):
            continue
        for h in n.handlers:
            corps = ast.unparse(h.body)
            if 'np.full' in corps or '.mean()' in corps:
                out.append((n.lineno, corps.split('\n')[0][:88]))
    return out


class TestPredictionImpossible(unittest.TestCase):

    def test_PI1_LE_RELEVE_voit_un_repli_constant_et_laisse_les_autres(self):
        """⚠️⚠️ CE CONTROLE PASSE AVANT LES AUTRES. Un relevé qui ne verrait
        aucun repli rendrait `PI-2` vert sur un fichier qui les porte tous :
        *il attesterait sans surveiller.* Il recoit donc les deux sens."""
        fautif = ast.parse(
            "def f(m, X, df, col):\n"
            "    try:\n"
            "        p = m.predict(X)\n"
            "    except Exception:\n"
            "        p = np.full(len(df), df[col].mean())\n"
            "    return p\n")
        self.assertEqual(
            len(_replis_constants(fautif)), 1,
            "un `except` qui remplace la prediction par une moyenne n'est "
            "pas vu : tout le controle repose sur ce relevé")
        #: ⚠️ SECOND SENS : les trois formes SAINES sont laissees.
        sains = ast.parse(
            "def a(m, X):\n"
            "    try:\n"
            "        p = m.predict(X)\n"
            "    except Exception as e:\n"
            "        raise ValueError('refus') from e\n"
            "def b(m, X):\n"
            "    try:\n"
            "        p = m.predict(X)\n"
            "    except Exception:\n"
            "        p = None\n"
            "def c(m, X):\n"
            "    try:\n"
            "        p = m.predict(X)\n"
            "    except Exception as e:\n"
            "        logger.error('refus %s', e)\n"
            "        p = None\n")
        self.assertEqual(
            _replis_constants(sains), [],
            "un `except` qui LEVE, qui pose `None` ou qui journalise est "
            "accuse : le controle accuse au lieu de surveiller")
        print("    PI-1 releve : 1 repli constant vu, 3 formes saines "
              "laissees")

    def test_PI2_SCEAU_aucun_repli_CONSTANT_dans_le_perimetre(self):
        """⚠️⚠️ LE SCEAU DE CLASSE, ET SON ASSIETTE EST TOUT LE PERIMETRE.
        Le limiter a `a3_glm` reviendrait a surveiller l'endroit qu'on vient
        de nettoyer -- or le meme geste existe partout ou un modele
        predit."""
        fichiers = _fichiers_de_production()
        self.assertGreater(
            len(fichiers), 50,
            f"l'assiette ne contient que {len(fichiers)} fichier(s) : le "
            f"relevé de production est casse, ce controle n'atteste rien")
        fautifs = []
        for rel in fichiers:
            try:
                arbre = ast.parse((_RACINE / rel).read_text(
                    encoding='utf-8', errors='replace'))
            except (SyntaxError, OSError):
                continue
            for li, code in _replis_constants(arbre):
                fautifs.append(f"{rel}:{li} -> {code}")
        self.assertEqual(
            fautifs, [],
            f"{len(fautifs)} `except` remplacent une prediction par une "
            f"CONSTANTE : le tarif devient plat et les metriques sont "
            f"mesurees sur ce plat. {fautifs[:4]}")
        print(f"    PI-2 SCEAU : 0 repli constant sur {len(fichiers)} "
              f"fichiers de production")

    def test_PI3_SCEAU_sur_le_PRIX_une_prediction_impossible_LEVE(self):
        """⚠️⚠️ LE CHEMIN DU PRIX, MESURE PAR EXECUTION. La frequence predite
        entre directement dans `prime_pure` : la fabriquer, c'est fabriquer
        un PRIX. Ce controle fait lever le `predict` du modele de frequence
        et exige une exception -- pas un tarif plat sous `success=True`."""
        from direction_non_vie.tarification.a3_glm.agent import (
            PredictionImpossible,
        )
        df, vars_pred, col_expo, agent = _chaine_a3()

        class _Casse:
            def __init__(self, vrai):
                self._vrai = vrai

            def __getattr__(self, nom):
                return getattr(self._vrai, nom)

            #: ⚠️ LA SIGNATURE EST CELLE DU SITE REEL -- `predict(X,
            #: offset=...)`. Une doublure qui accepterait n'importe quoi
            #: passerait aussi bien sur un site qui n'existe plus.
            def predict(self, X, offset=None):
                raise ValueError(
                    f'le modele refuse ces {len(X)} lignes '
                    f'(offset {"fourni" if offset is not None else "absent"})')

        #: ⚠️⚠️ ON REMET LE MODELE EN PLACE. La chaine est calculee UNE fois
        #: et partagee : sans cette restauration, ce test laisse l'agent
        #: casse et c'est `PI-4` -- la contre-epreuve -- qui echoue, en
        #: accusant le correctif d'une panne que ce test a posee. *Un test
        #: qui abime l'etat commun fait mentir son voisin.*
        _vrai_modele = agent.modeles['poisson']
        agent.modeles['poisson'] = _Casse(_vrai_modele)
        try:
            with self.assertRaises(PredictionImpossible) as ctx:
                agent._calculer_predictions(df, vars_pred, col_expo)
        finally:
            agent.modeles['poisson'] = _vrai_modele
        self.assertIn('prime pure', str(ctx.exception),
                      "le message ne dit pas POURQUOI on refuse : que la "
                      "valeur entrerait telle quelle dans la prime pure")
        print("    PI-3 SCEAU : le prix LEVE au lieu de fabriquer une "
              "frequence")

    def test_PI4_CONTRE_EPREUVE_le_chemin_SAIN_ne_bouge_pas(self):
        """⚠️ Le second sens, et il est indispensable : un correctif qui
        ferait lever le cas SAIN aurait remplace un defaut par une panne."""
        df, vars_pred, col_expo, agent = _chaine_a3()
        pred = agent._calculer_predictions(df, vars_pred, col_expo)
        import numpy as np
        fa = np.asarray(pred.get('frequence_annuelle', []), dtype=float)
        self.assertGreater(
            len(np.unique(fa)), 100,
            f"le tarif sain ne porte que {len(np.unique(fa))} valeur(s) "
            f"distincte(s) : il est PLAT alors que rien n'a echoue")
        print(f"    PI-4 contre-epreuve : {len(np.unique(fa))} valeurs "
              f"distinctes sur le chemin sain")


_CACHE = {}


def _chaine_a3():
    """A1 -> A2 -> A3 sur un portefeuille SYNTHETIQUE, une seule fois.

    ⚠️⚠️ LES ARGUMENTS DE `_calculer_predictions` SONT CAPTURES, JAMAIS
    RECONSTRUITS. Ma premiere sonde les reconstruisait de son cote : elle a
    leve `KeyError: ['risque_historique'] not in index` et rendu une prime
    pure de 0,00 EUR. *Une sonde qui n'emprunte pas le chemin reel ne mesure
    pas ce chemin.*
    """
    if 'v' in _CACHE:
        return _CACHE['v']
    import logging
    import tempfile
    import warnings

    import numpy as np
    import pandas as pd

    from core.plan_tarifaire import PlanTarifaire
    from core.qualite_donnees import preambule_qualite
    from direction_non_vie.tarification.a1_ingestion.agent import (
        AgentA1Ingestion,
    )
    from direction_non_vie.tarification.a2_preprocessing.agent import (
        AgentA2Preprocessing,
    )
    from direction_non_vie.tarification.a3_glm import agent as A3M

    warnings.filterwarnings('ignore')
    niveau = logging.getLogger().level
    logging.disable(logging.CRITICAL)
    tmp = tempfile.mkdtemp(prefix='pi_')
    #: ⚠️⚠️ LES COLONNES SONT CELLES QUE `plans/auto.yaml` DECLARE. Ma
    #: premiere redaction inventait ses propres noms : A3 n'atteignait
    #: jamais l'etape 5 et la capture restait vide (`KeyError: 'args'`).
    #: *Un portefeuille qui ne correspond pas au plan ne traverse pas la
    #: chaine -- et un test qui ne traverse rien n'atteste rien.*
    rng = np.random.default_rng(20260913)
    n = 4000
    df0 = pd.DataFrame({
        'id_contrat': np.arange(1, n + 1), 'date_echeance': '2023-01-01',
        'exposition': np.clip(rng.beta(1.3, 1.5, n), 0.02, 1.0),
        'age': rng.integers(18, 85, n),
        'bonus_malus': np.clip(rng.normal(0.75, 0.20, n), 0.50, 3.50),
        'anciennete_permis': rng.integers(0, 50, n),
        'puissance_fiscale': rng.integers(3, 20, n),
        'age_vehicule': rng.integers(0, 25, n),
        'valeur_venale': np.exp(rng.normal(9.3, 0.6, n)),
        'garantie': rng.choice(['Tiers', 'TousRisques'], n),
        'carburant': rng.choice(['Essence', 'Diesel', 'Electrique'], n),
        'csp': rng.choice(['Cadre', 'Employe', 'Retraite'], n),
        'usage': rng.choice(['Prive', 'Pro'], n),
        'antecedents_sinistres_n1': rng.poisson(0.25, n),
        'kilometrage_annuel': rng.integers(2000, 40000, n),
        'milieu_geographique': rng.choice(
            ['Urbain', 'Periurbain', 'Rural'], n)})
    #: ⚠️⚠️ LA SINISTRALITE EST VOLONTAIREMENT ELEVEE, ET C'EST NECESSAIRE.
    #: A 0,11 sinistre par contrat-an, le GLM de COUT ne s'ajuste pas sur
    #: cette graine : `_calculer_predictions` leve alors legitimement, et
    #: `PI-4` -- la contre-epreuve du chemin SAIN -- n'a plus de chemin sain
    #: a exercer. *Une contre-epreuve doit porter sur un cas qui marche,
    #: sinon elle mesure autre chose que ce qu'elle annonce.*
    _lam = 0.45 * np.exp(0.30 * (df0['bonus_malus'] - 0.75)
                         - 0.006 * (df0['age'] - 45))
    df0['nb_sinistres'] = rng.poisson(_lam * df0['exposition'])
    df0['cout_total_sinistres'] = np.where(
        df0['nb_sinistres'] > 0,
        rng.gamma(2.0, 850.0, n) * df0['nb_sinistres'], 0.0)
    plan = PlanTarifaire.depuis_yaml(str(_RACINE / 'plans' / 'auto.yaml'))
    r1 = AgentA1Ingestion(base_path=tmp + '/d', audit_path=tmp + '/a',
                          verbose=False).run(
        branche='non_vie', sous_branche='auto', dataframe=df0, plan=plan)
    rq = preambule_qualite(r1.get('dataframe'), plan,
                           horodatage='2026-09-13T00:00:00')
    r2 = AgentA2Preprocessing(verbose=False).run(
        result_a1={**r1, 'dataframe': rq.dataframe_propre}, plan=plan)

    capture = {}
    vrai = A3M.AgentA3GLM._calculer_predictions

    def _espion(self, d, v, c):
        capture['args'] = (d, v, c)
        return vrai(self, d, v, c)

    agent = A3M.AgentA3GLM(verbose=False)
    A3M.AgentA3GLM._calculer_predictions = _espion
    try:
        agent.run(result_a2=r2, plan=plan,
                  col_frequence=plan.cible_frequence,
                  col_cout=plan.cible_cout, generer_graphiques=False)
    finally:
        A3M.AgentA3GLM._calculer_predictions = vrai
        logging.disable(niveau)
    d, v, c = capture['args']
    _CACHE['v'] = (d, v, c, agent)
    return _CACHE['v']


if __name__ == '__main__':
    unittest.main(verbosity=2)
