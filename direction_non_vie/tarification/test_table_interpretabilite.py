"""Controles positifs — `a6/C9` : la table qui DECIDE couvre ce qui est PRODUIT.

CE QUE CE FICHIER PROUVE, ET POURQUOI IL EXISTE
────────────────────────────────────────────────

`INTERPRETABILITE` pese **de 10 % a 30 %** du score multicriteres selon le
profil (`performance` 10 %, defaut `equilibre` 20 %, `auditabilite_s2` 30 %).
Ce score choisit le modele de production, c'est-a-dire **le tarif**. La table
n'est pas documentaire.

⚠️ CETTE FOURCHETTE EST DERIVEE, PAS RECOPIEE, et elle m'a corrige : j'avais
ecrit « au moins 15 % partout » avant de la mesurer, sur la foi du profil par
defaut. Le controle C9-9 est tombe sur `performance` a 10 %. *Deriver d'abord,
ecrire ensuite -- meme quand le chiffre parait evident.*

═══ LE DEFAUT, MESURE LE 30/08/2026 ═══

Elle portait **trois valeurs par defaut**, une par agent appelant :

```
  A3 -> INTERPRETABILITE.get(nom, 0.5)
  A4 -> INTERPRETABILITE.get(nom, 0.6)
  A5 -> INTERPRETABILITE.get(nom, 0.7)
```

⚠️⚠️ UN MODELE ABSENT RECEVAIT DONC UNE INTERPRETABILITE QUI DEPENDAIT DE QUEL
AGENT L'AVAIT PRODUIT, ET NON DE CE QU'EST LE MODELE. Et le cas n'etait pas
theorique : `xgboost_tweedie` est calibre a **chaque** run d'A4 (59 occurrences
dans une gate reelle du 30/08), il entre au classement, et il etait **absent de
la table**. Sur une fixture ou stabilite et RMSE sont EGALES entre deux rivaux,
pour que le seul ecart vienne du defaut :

```
  defaut=0.5 (celui ecrit pour A3)  -> #1 ML_XGBOOST           marge +0.0138
  defaut=0.6 (celui d'A4, ACTIF)    -> #1 ML_XGBOOST_TWEEDIE   marge +0.0062
  defaut=0.7 (celui ecrit pour A5)  -> #1 ML_XGBOOST_TWEEDIE   marge +0.0262
```

**Le vainqueur bascule d'une ligne de defaut a l'autre.** Un pas de 0,1 vaut
0,02 sur le score global, quand les marges #1-#2 mesurees sur cet agent (lot
`a6/C3`, quatre portefeuilles) valaient **0,008 · 0,016 · 0,021**.

═══ L'ASYMETRIE ENTRE VOISINS, QUI A DESIGNE LE TROU ═══

Deux tables jumelles, meme forme, meme risque de derive :

| table | `xgboost_tweedie` | ce qu'elle decide | defaut declare ? |
|---|---|---|---|
| `FAMILLES_MODELES_ML` (A4) | present | un LIBELLE de famille | oui, docstring + `'Autre ML'` |
| `INTERPRETABILITE` (A6) | ABSENT | le modele qui TARIFE | non, trois defauts nus |

*La table decorative etait gardee et complete ; celle qui decide ne l'etait
pas.* Et **aucun test n'exercait la table** : les 14 sites de fixture qui
portent la cle `interpretabilite` la fournissent en dur.

═══ CE QUE LE CORRECTIF FAIT, ET CE QU'IL NE FAIT PAS ═══

⚠️⚠️ IL NE DEPLACE AUCUN EURO, ET C'EST VERIFIE CI-DESSOUS. La valeur declaree
pour `xgboost_tweedie` est **0.60** — exactement ce que le defaut d'A4 rendait.
*Le lot declare ce qui etait accidentel.*

⚠️ IL N'EXIGE PAS L'EGALITE DES DEUX ENSEMBLES, MAIS LA COUVERTURE. La table a
le droit d'etre PLUS LARGE que ce que les agents calibrent : `random_forest`,
`quantile_50` et `quantile_90` ont une fabrique et des hyperparametres dans A4
sans etre dans sa liste de candidats. Leurs valeurs sont des jugements deja
poses ; les effacer ne fermerait rien et perdrait une decision. *Le sens
interdit est l'autre : un modele PRODUIT et absent.*

⚠️ BORNE DECLAREE. Les trois listes ci-dessous sont celles que les agents
DECLARENT. Un agent qui ecrirait une cle de `metriques` hors de sa liste
echapperait a ce controle statique -- c'est pourquoi la levee existe AUSSI a
l'execution, et qu'elle est prouvee ici. Les deux filets sont necessaires.
"""

from __future__ import annotations

import ast
import pathlib
import unittest
from unittest import mock

from direction_non_vie.tarification.a6_comparaison.agent import (
    INTERPRETABILITE,
    POIDS_CRITERES,
    PROFILS_PONDERATION,
    AgentA6Comparaison,
    interpretabilite_de,
)

_TARIF = pathlib.Path(__file__).resolve().parent


def _arbre(chemin_relatif: str) -> ast.Module:
    """⚠️ RESOLU VERS UN CHEMIN REEL : un fichier absent fait TOMBER le test
    plutot que de reduire son assiette en silence."""
    chemin = _TARIF / chemin_relatif
    if not chemin.is_file():
        raise AssertionError(
            f"Fichier introuvable : {chemin}. L'assiette de ce controle serait "
            f"reduite sans que personne ne le sache.")
    return ast.parse(chemin.read_text(encoding='utf-8'))


def _modeles_declares_par_a4() -> list[str]:
    """La liste `modeles_a_calibrer` d'A4, lue par AST -- jamais recopiee."""
    for n in ast.walk(_arbre('a4_ml/agent.py')):
        if isinstance(n, ast.Assign) and any(
                isinstance(x, ast.Name) and x.id == 'modeles_a_calibrer'
                for x in n.targets):
            return [e.elts[0].value for e in n.value.elts]
    raise AssertionError("`modeles_a_calibrer` introuvable dans A4 : le "
                         "controle ne porte plus sur rien.")


def _modeles_declares_par_a5() -> list[str]:
    """Le defaut du parametre `modeles` de `A5.run`, lu par AST."""
    for n in ast.walk(_arbre('a5_deep_learning/agent.py')):
        if isinstance(n, ast.FunctionDef) and n.name == 'run' and n.args.defaults:
            portants = n.args.args[-len(n.args.defaults):]
            for arg, defaut in zip(portants, n.args.defaults):
                if arg.arg == 'modeles' and isinstance(defaut, ast.Tuple):
                    return [e.value for e in defaut.elts]
    raise AssertionError("Le parametre `modeles` d'A5 introuvable : le "
                         "controle ne porte plus sur rien.")


def _modeles_glm_lus_par_a6() -> list[str]:
    """La boucle litterale `for nom in [...]` du catalogue GLM, lue par AST."""
    for n in ast.walk(_arbre('a6_comparaison/agent.py')):
        if (isinstance(n, ast.For) and isinstance(n.target, ast.Name)
                and n.target.id == 'nom' and isinstance(n.iter, ast.List)):
            return [e.value for e in n.iter.elts]
    raise AssertionError("La boucle GLM d'A6 introuvable : le controle ne "
                         "porte plus sur rien.")


def _tous_les_modeles_produits() -> dict[str, str]:
    """{nom du modele: agent qui le declare} pour les trois producteurs."""
    produits = {}
    for agent, noms in (('A3', _modeles_glm_lus_par_a6()),
                        ('A4', _modeles_declares_par_a4()),
                        ('A5', _modeles_declares_par_a5())):
        for nom in noms:
            produits[nom] = agent
    return produits


def _a4(metriques: dict) -> dict:
    return {'success': True, 'metriques': metriques, 'col_cible': 'prime_pure'}


def _a2(n: int = 300) -> dict:
    """Le minimum qu'`A6.run` exige — il lit `branche` puis `dataframe`."""
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(7)
    expo = rng.uniform(0.3, 1.0, n)
    return {'success': True, 'branche': 'auto',
            'dataframe': pd.DataFrame({
                'prime_pure': rng.gamma(6.0, 70.0, n),
                'nb_sinistres': rng.poisson(0.08 * expo, n).astype(float),
                'exposition': expo,
                'age': rng.integers(18, 75, n).astype(float),
                'annee_souscription': rng.choice([2021, 2022, 2023], n)})}


class TestLaTableCouvreToutCeQuiEstPRODUIT(unittest.TestCase):
    """`a6/C9` — LE CONTROLE QUI FERME, et il est DERIVE, jamais recopie."""

    def test_LE_TEST_QUI_FERME_aucun_modele_produit_n_est_absent(self):
        """⚠️⚠️ IL TOMBERA LE JOUR OU UN AGENT AJOUTERA UN MODELE SANS LE
        DECLARER ICI -- c'est-a-dire AVANT que ce modele ne recoive une
        interpretabilite que personne n'a choisie."""
        produits = _tous_les_modeles_produits()
        absents = {n: a for n, a in produits.items() if n not in INTERPRETABILITE}
        self.assertEqual(
            absents, {},
            f"{len(absents)} modele(s) calibre(s) en production sans "
            f"interpretabilite declaree : {absents}. Leur valeur serait "
            f"decidee par un defaut, donc par leur AGENT PRODUCTEUR et non par "
            f"ce qu'ils sont.")
        print(f"    C9-1 {len(produits)} modeles produits (A3 {len(_modeles_glm_lus_par_a6())}, "
              f"A4 {len(_modeles_declares_par_a4())}, A5 {len(_modeles_declares_par_a5())}), "
              f"0 absent de la table")

    def test_le_cas_qui_a_ouvert_le_constat_est_bien_couvert(self):
        """⚠️ `xgboost_tweedie` est le SEUL trou vivant qu'avait la table, et
        il tournait a chaque run. On le nomme, pour qu'un futur retrait le
        fasse tomber sous son propre nom."""
        self.assertIn('xgboost_tweedie', _modeles_declares_par_a4(),
                      "premisse : A4 ne calibre plus `xgboost_tweedie`, ce "
                      "controle ne prouve plus rien")
        self.assertIn('xgboost_tweedie', INTERPRETABILITE)
        print(f"    C9-2 `xgboost_tweedie` calibre par A4 ET declare : "
              f"{INTERPRETABILITE['xgboost_tweedie']}")


class TestAucunEuroDeplace(unittest.TestCase):
    """⚠️⚠️ CONDITION DE LOT : ce correctif ne doit RIEN changer aux valeurs."""

    #: Le defaut qu'A4 appliquait avant ce lot, ecrit ici comme TEMOIN.
    _DEFAUT_A4_AVANT = 0.60

    def test_la_valeur_declaree_REPRODUIT_l_ancien_defaut(self):
        """⚠️ La table est desormais explicite la ou elle etait accidentelle —
        et l'accident tombait juste. *On declare ce qui etait implicite ; on ne
        corrige pas une valeur.*"""
        self.assertEqual(INTERPRETABILITE['xgboost_tweedie'],
                         self._DEFAUT_A4_AVANT,
                         "la valeur declaree differe de ce que le defaut "
                         "rendait : ce lot DEPLACERAIT un prix")
        self.assertEqual(INTERPRETABILITE['xgboost_tweedie'],
                         INTERPRETABILITE['xgboost'],
                         "meme structure, meme lisibilite : seul l'objectif "
                         "change entre les deux")
        print(f"    C9-3 valeur declaree = ancien defaut = "
              f"{self._DEFAUT_A4_AVANT} — aucun euro deplace")

    def test_le_score_publie_par_un_RUN_reel_porte_cette_valeur(self):
        """⚠️ La table peut etre juste sans que le score la lise. On lit le
        score, pas la table."""
        agent = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp',
                                   verbose=False)
        catalogue = agent._agreger_resultats(
            None,
            _a4({'xgboost': {'gini_test': 0.221, 'gini_train': 0.232,
                             'rmse_test': 389.0, 'overfit_ratio': 1.05},
                 'xgboost_tweedie': {'gini_test': 0.2245, 'gini_train': 0.235,
                                     'rmse_test': 388.0, 'overfit_ratio': 1.047}}),
            None, col_cible='prime_pure')[0]
        note = agent._calculer_scores_multicriteres(catalogue, POIDS_CRITERES)
        tw = next(m for m in note if m['modele'] == 'ML_XGBOOST_TWEEDIE')
        self.assertEqual(tw['score_interpretabilite'], self._DEFAUT_A4_AVANT)
        print(f"    C9-4 run reel : score_interpretabilite = "
              f"{tw['score_interpretabilite']} pour ML_XGBOOST_TWEEDIE")


class TestUnModeleNonDeclareLEVE(unittest.TestCase):
    """⚠️⚠️ LE SECOND SENS LE PLUS IMPORTANT : le controle doit POUVOIR tomber.

    On retire l'entree de la table, comme si personne ne l'avait declaree, et
    la chaine doit refuser de tarifer plutot que d'inventer une valeur.
    """

    def test_la_porte_unique_LEVE_au_lieu_de_deviner(self):
        self.assertAlmostEqual(interpretabilite_de('xgboost'), 0.60)
        with self.assertRaises(ValueError) as leve:
            interpretabilite_de('un_modele_jamais_declare')
        motif = str(leve.exception)
        self.assertIn('un_modele_jamais_declare', motif,
                      'le motif ne nomme pas le modele fautif')
        self.assertIn('INTERPRETABILITE', motif,
                      'le motif ne nomme pas la table a completer')
        self.assertIn('a6_comparaison/agent.py', motif,
                      'le motif ne dit pas OU declarer la valeur')
        print(f"    C9-5 levee : « {motif[:60]}... » — nomme le modele, la "
              f"table ET le fichier")

    def test_A6_ECHOUE_PROPREMENT_il_n_explose_pas(self):
        """⚠️⚠️ UNE LEVEE QUI REMONTE JUSQU'A L'APPELANT SERAIT UN PLANTAGE.
        `run` l'intercepte : `success=False` et le motif au clair. *L'agent
        refuse de tarifer, il ne casse pas le pipeline.*"""
        agent = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp',
                                   verbose=False)
        sans_tweedie = {k: v for k, v in INTERPRETABILITE.items()
                        if k != 'xgboost_tweedie'}
        cible = ('direction_non_vie.tarification.a6_comparaison.agent'
                 '.INTERPRETABILITE')
        with mock.patch(cible, sans_tweedie):
            r = agent.run(
                result_a2=_a2(), result_a3=None,
                result_a4=_a4({'xgboost_tweedie': {
                    'gini_test': 0.22, 'gini_train': 0.23,
                    'rmse_test': 388.0, 'overfit_ratio': 1.05}}),
                result_a5=None, col_cible='prime_pure',
                generer_graphiques=False, generer_rapport_equipe=False)
        self.assertFalse(r['success'],
                         "A6 a tarife avec un modele dont l'interpretabilite "
                         "n'est declaree nulle part")
        self.assertIn('xgboost_tweedie', str(r.get('erreur', '')),
                      "l'erreur ne nomme pas le modele : l'actuaire ne sait "
                      "pas quoi declarer")
        print("    C9-6 second sens : entree retiree -> success=False, le "
              "motif nomme le modele — aucun plantage")

    def test_une_table_PLUS_LARGE_que_la_production_ne_leve_PAS(self):
        """⚠️⚠️ L'INVARIANT EST UNE COUVERTURE, PAS UNE EGALITE. Exiger
        l'egalite forcerait a effacer trois jugements deja poses -- et *on ne
        supprime pas une question en supprimant ce qui la porte*."""
        produits = set(_tous_les_modeles_produits())
        plus_larges = sorted(set(INTERPRETABILITE) - produits)
        self.assertEqual(
            plus_larges, ['quantile_50', 'quantile_90', 'random_forest'],
            f"les entrees non produites ont change : {plus_larges}. Ce "
            f"controle les NOMME pour que leur presence reste une decision "
            f"lisible, jamais un residu.")
        for nom in plus_larges:
            with self.subTest(modele=nom):
                self.assertIsInstance(interpretabilite_de(nom), float)
        print(f"    C9-7 second sens : {len(plus_larges)} entrees plus larges "
              f"que la production ({', '.join(plus_larges)}) — aucune levee")


class TestLaTableNAPlusDeDefautDuTout(unittest.TestCase):
    """⚠️⚠️ LE DEFAUT ETAIT LE SUJET : il ne doit pas revenir par une porte."""

    def test_aucun_appelant_ne_reintroduit_un_defaut(self):
        """⚠️ Mesure par AST sur A6 : plus aucun `INTERPRETABILITE.get(...)`
        avec repli. C'etait la forme exacte des trois defauts 0.5 / 0.6 / 0.7."""
        avec_repli = []
        for n in ast.walk(_arbre('a6_comparaison/agent.py')):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'get'
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == 'INTERPRETABILITE'
                    and len(n.args) > 1):
                avec_repli.append(n.lineno)
        self.assertEqual(
            avec_repli, [],
            f"un defaut est revenu, ligne(s) {avec_repli} : un modele non "
            f"declare recevrait de nouveau une valeur que personne n'a choisie")
        print("    C9-8 0 `INTERPRETABILITE.get(nom, defaut)` — les trois "
              "defauts 0.5 / 0.6 / 0.7 ont disparu")

    def test_le_poids_du_critere_justifie_la_severite(self):
        """⚠️ La severite se JUSTIFIE par un chiffre, pas par une opinion : si
        ce critere pesait 0 quelque part, lever y serait disproportionne.

        ⚠️⚠️ ET J'AVAIS ECRIT LE SEUIL AVANT DE LE DERIVER, UNE FOIS DE PLUS.
        J'ai pose « au moins 15 % partout » sur la foi du profil par defaut a
        20 % : le profil `performance` pese **10 %**, et le test est tombe. La
        borne exacte est **0,10 a 0,30**.
        *Meme a 0,10, l'argument tient et c'est ce qui est verifie ici* : un pas
        de 0,1 d'interpretabilite vaut alors 0,01 sur le score global, quand la
        plus petite marge #1-#2 mesuree sur cet agent valait **0,008**. Le
        critere ne peut donc etre nul dans AUCUN profil.
        """
        poids = {nom: p['interpretabilite']
                 for nom, p in PROFILS_PONDERATION.items()}
        self.assertTrue(
            all(p > 0 for p in poids.values()),
            f"un profil annule l'interpretabilite : {poids}. Lever pour une "
            f"valeur qui ne pese rien serait disproportionne.")
        effet_mini = min(poids.values()) * 0.1
        self.assertGreater(
            effet_mini, 0.008,
            f"un pas de 0,1 vaut {effet_mini:.4f} sur le profil le plus "
            f"leger — moins que la plus petite marge #1-#2 mesuree (0,008) : "
            f"la severite ne serait plus justifiee par la mesure")
        print(f"    C9-9 poids de l'interpretabilite : de "
              f"{min(poids.values()):.0%} a {max(poids.values()):.0%} selon le "
              f"profil ; effet minimal d'un pas de 0,1 = {effet_mini:.4f} "
              f"contre une marge mesuree de 0,008")


if __name__ == '__main__':
    unittest.main()
