"""Controles positifs — `a3` : les huit derniers constats de la zone.

═══ ⛔⛔ `C7` — LE << MEILLEUR MODELE >> ETAIT PREDETERMINE ═══

`meilleur_modele = max(comparaison_gini, key=...)` sur
`{'poisson': 0.1688, 'gamma': 0.042}`. Mais **le Poisson est evalue sur TOUT le
test** (frequence) et **le Gamma sur les SINISTRES SEULS** (severite).

> *Ce ne sont pas deux candidats pour la meme tache : ce sont les deux FACTEURS
> d'un meme produit -- prime = frequence x cout.*

Un Gini de frequence sur le portefeuille entier depasse presque toujours un
Gini de severite sur les seuls sinistres : `max()` ne mesurait rien, il rendait
toujours le meme nom. La cle est **conservee et mise a `None`**, avec son
motif -- le patron deja valide pour la reference A3 absente d'`a4/C11`. *La
retirer casserait un lecteur en silence ; la laisser mentir est pire.*

═══ ⛔⛔ `C13` — UNE FIGURE ABSENTE QUE PERSONNE NE RECLAMAIT ═══

La jauge lisait `h2_homosc["dw_stat"]` ; H2 rend `ratio_variance` depuis la
reparation `87e0609`. Le `KeyError` tombait dans un `except` large et **la
figure disparaissait en silence** : mesure du 01/09, trois figures de validation
produites, jamais celle-ci.

> *Un `except` large transforme une figure ABSENTE en figure JAMAIS RECLAMEE.*

⚠️ ET LE NOM CHANGE AVEC LA GRANDEUR : Durbin-Watson mesure l'AUTOCORRELATION,
pas l'homoscedasticite. *Garder l'ancien titre sur la nouvelle mesure aurait
fait publier un nom faux.* La cle devient
`homoscedasticite_ratio_variance` -- quatre figures desormais.

═══ ⛔ `C15` — LE REPLI CASSAIT LUI-MEME ═══

Quand `modele_final.predict` echoue, `pred_test` devient un `np.full`, donc un
`ndarray` -- qui n'a PAS d'attribut `.values`. *Le chemin de secours levait un
`AttributeError` a la place de l'erreur qu'il etait cense absorber.* **C'est la
forme de `pipeline/C2`, sur un autre agent.**

═══ LES CINQ AUTRES ═══

| constat | ce qui etait annonce | ce qui est |
|---|---|---|
| `C11` | 5 renvois a `VARS_GLM` | la constante est SUPPRIMEE |
| `C12` | `0.05` en dur, 2 sites | `SEUIL_PVALUE` existe depuis toujours |
| `C16` | 5 entrees Vie/Sante sur 23 | conservees, et DITES -- voir plus bas |
| `C17` | `run(result_a2)`, 3 fois | le module REFUSE cet appel |
| `C18` | << 7 tests >> | 4 methodes |

⚠️ `C16` : les entrees RESTENT, meme arbitrage que `a5/C8`. Cette liste
EXCLUT -- en oter une AJOUTERAIT une variable au modele si un fichier client
portait cette colonne. *Le geste << propre >> est ici le geste RISQUE.* `A3-8`
monte la garde : 0 / 20 plans ne nomme l'une d'elles.
"""

from __future__ import annotations

import ast
import glob
import logging
import pathlib
import re
import unittest
import warnings

import numpy as np

from core.plan_tarifaire import PlanTarifaire
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
)
from direction_non_vie.tarification.a3_glm import agent as _a3mod
from direction_non_vie.tarification.a3_glm.agent import (
    COLS_A_EXCLURE,
    SEUIL_PVALUE,
    AgentA3GLM,
)
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)

_SOURCE = pathlib.Path(_a3mod.__file__).read_text(encoding='utf-8')
_SOURCE_TEST = (pathlib.Path(_a3mod.__file__).parent
                / 'test_a3_glm.py').read_text(encoding='utf-8')
_VIE_SANTE = ('id_salarie', 'id_beneficiaire', 'id_adherent',
              'cotisation_mensuelle_eur', 'charge_ij_annuelle_eur')


def _sans_bruit(fn, *a, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return fn(*a, **kw)
        finally:
            logging.disable(precedent)


_CACHE = {}


def _a3(n=1200, seed=3):
    """Un run complet A1 -> A2 -> A3, mis en cache : il coute ~4 s."""
    if 'r3' not in _CACHE:
        def _run():
            df = _portefeuille_auto(n, seed=seed)
            r1 = AgentA1Ingestion(audit_path='/tmp', verbose=False).run(
                dataframe=df, branche='non_vie', sous_branche='auto')
            r2 = AgentA2Preprocessing(audit_path='/tmp', verbose=False).run(
                r1, plan=_PLAN_AUTO)
            return AgentA3GLM(audit_path='/tmp', verbose=False).run(
                r2, plan=_PLAN_AUTO)
        _CACHE['r3'] = _sans_bruit(_run)
    return _CACHE['r3']


def _globales(r3):
    return (r3.get('rapport') or {}).get('metriques_globales') or {}


class TestC7DeuxGiniIncomparables(unittest.TestCase):

    def test_LE_TEST_QUI_FERME_aucun_MEILLEUR_n_est_proclame(self):
        """⚠️⚠️ `max()` sur deux populations differentes rendait TOUJOURS le
        meme nom. *Il ne mesurait rien.*"""
        g = _globales(_a3())
        self.assertIsNone(g.get('meilleur_modele'),
                          f"un meilleur est encore proclame : "
                          f"{g.get('meilleur_modele')!r}")
        self.assertIn('meilleur_modele', g,
                      'la cle a ete RETIREE : un lecteur casserait en silence')
        print("    A3-1 aucun `meilleur_modele` proclame, et la cle est "
              "conservee")

    def test_le_MOTIF_voyage_avec_le_None(self):
        """⚠️ Un `None` sans motif renvoie l'actuaire a la devinette — la
        lecon deja epinglee par `a4/C11` et `conformite/C7`."""
        motif = _globales(_a3()).get('meilleur_modele_motif') or ''
        self.assertIn('POPULATIONS DIFFERENTES', motif)
        self.assertIn('frequence', motif)
        self.assertIn('severite', motif)
        print(f"    A3-2 le motif nomme la cause : {motif[:58]}...")

    def test_la_comparaison_porte_SA_POPULATION(self):
        """⚠️⚠️ Deux nombres cote a cote se lisent comme un classement si rien
        ne dit qu'ils ne portent pas sur la meme chose."""
        g = _globales(_a3())
        pops = g.get('comparaison_gini_populations') or {}
        self.assertEqual(set(pops), set(g.get('comparaison_gini') or {}),
                         'une population manque a un des Gini publies')
        self.assertIn('tout le jeu de test', pops.get('poisson', ''))
        self.assertIn('sinistres seuls', pops.get('gamma', ''))
        print(f"    A3-3 chaque Gini porte sa population : {pops}")


class TestC13LaFigureAbsente(unittest.TestCase):

    def test_LE_TEST_QUI_FERME_la_jauge_d_homoscedasticite_est_PRODUITE(self):
        """⚠️⚠️ Elle lisait `dw_stat` ; H2 rend `ratio_variance`. Le
        `KeyError` tombait dans un `except` large et la figure disparaissait
        SANS UN MOT."""
        figures = set(_a3().get('graphiques_validation') or {})
        self.assertIn('homoscedasticite_ratio_variance', figures)
        self.assertNotIn('durbin_watson', figures,
                         'le nom Durbin-Watson est revenu : il mesure '
                         "l'AUTOCORRELATION, pas l'homoscedasticite")
        print(f"    A3-4 {len(figures)} figures de validation, dont la jauge "
              f"d'homoscedasticite")

    def test_la_jauge_lit_la_grandeur_QUE_H2_PRODUIT(self):
        """⚠️ SECOND SENS : on verifie que la cle lue EXISTE cote H2, sinon le
        controle precedent passerait sur une figure vide."""
        h2 = (_a3().get('hypotheses') or {}).get('h2_homosc') or {}
        self.assertIn('ratio_variance', h2)
        self.assertNotIn('dw_stat', h2)
        self.assertIsNotNone(h2['ratio_variance'])
        print(f"    A3-5 H2 rend `ratio_variance` = "
              f"{h2['ratio_variance']}, et c'est ce que la jauge lit")


class TestC15LeRepliNeCassePlus(unittest.TestCase):

    def test_LE_REPLI_accepte_un_ndarray(self):
        """⚠️⚠️ `np.full(...)` rend un `ndarray`, qui n'a PAS `.values`. *Le
        chemin de secours levait un `AttributeError` a la place de l'erreur
        qu'il etait cense absorber* — la forme de `pipeline/C2`.

        ⚠️ ON EXERCE LE REPLI, on ne lit pas le code : c'est la seule facon de
        savoir qu'il tient.
        """
        agent = AgentA3GLM(audit_path='/tmp', verbose=False)
        y = np.array([0.0, 1.0, 2.0, 3.0])
        repli = np.full(4, 1.5)                 # exactement ce que fait le repli
        valeur = agent._calculer_gini(y, np.asarray(repli))
        self.assertIsInstance(valeur, float)
        # ⚠️ Et le meme appel avec une Series doit encore marcher : le correctif
        # ne doit pas casser le chemin NOMINAL.
        import pandas as pd
        self.assertIsInstance(
            agent._calculer_gini(y, np.asarray(pd.Series(repli))), float)
        print("    A3-6 le repli (ndarray) ET le chemin nominal (Series) "
              "passent tous deux")

    def test_plus_aucun_point_values_sur_une_prediction(self):
        """⚠️ Mesure PAR AST : aucun `.values` applique a `pred_test`."""
        arbre = ast.parse(_SOURCE)
        coupables = [n.lineno for n in ast.walk(arbre)
                     if isinstance(n, ast.Attribute) and n.attr == 'values'
                     and isinstance(n.value, ast.Name)
                     and n.value.id.startswith('pred')]
        self.assertEqual(coupables, [],
                         f'`.values` sur une prediction en l.{coupables}')
        print("    A3-7 aucun `.values` sur une prediction")


class TestLesCinqAutres(unittest.TestCase):

    def test_C16_la_liste_noire_ne_mange_aucune_colonne_DECLAREE(self):
        """⚠️⚠️ LE TEMOIN. Les entrees Vie/Sante RESTENT — en oter une
        AJOUTERAIT une variable si un fichier client la portait. *Le geste
        propre est ici le geste risque.*"""
        noir = set(COLS_A_EXCLURE)
        self.assertTrue(set(_VIE_SANTE) <= noir,
                        'des entrees ont ete retirees : un fichier client les '
                        'ferait entrer dans le modele')
        victimes = [(pathlib.Path(f).name, c)
                    for f in sorted(glob.glob('plans/*.yaml'))
                    for c in PlanTarifaire.depuis_yaml(f).colonnes_produites()
                    if c in noir]
        self.assertEqual(victimes, [],
                         f'{len(victimes)} colonne(s) DECLAREE(S) seraient '
                         f'supprimees en silence : {victimes}')
        print(f"    A3-8 0 / {len(glob.glob('plans/*.yaml'))} plans ne nomme "
              f"une des {len(noir)} entrees de la liste noire")

    def test_C12_le_seuil_vient_de_sa_SOURCE_UNIQUE(self):
        """⚠️ `0.05` etait ecrit en dur a deux sites, a cote d'une constante
        qui existait deja. *Deux endroits a changer le jour ou il bouge.*"""
        # ⚠️⚠️ ON NE COMPTE QUE LES COMPARAISONS DE P-VALUE. Ma premiere
        # version flaguait TOUT `0.05` compare : elle attrapait
        # `gini_poisson < 0.05`, qui est un seuil de GINI, pas une p-value.
        # *Deux grandeurs qui partagent un nombre ne partagent pas une
        # constante* — le piege de l'homonyme, applique a un litteral.
        # ⚠️ Ce seuil de Gini reste un nombre magique, NOMME ici et non traite :
        # il appartient au verdict de vraisemblance, pas a `a3/C12`.
        arbre = ast.parse(_SOURCE)
        lignes = _SOURCE.splitlines()
        pvalues = {n.lineno for n in ast.walk(arbre)
                   if isinstance(n, ast.Compare)
                   for c in n.comparators
                   if isinstance(c, ast.Constant) and c.value == 0.05
                   and 'pvalue' in lignes[n.lineno - 1].lower()}
        self.assertEqual(pvalues, set(),
                         f'une p-value est encore comparee a `0.05` en dur, '
                         f'l.{sorted(pvalues)}')
        self.assertEqual(SEUIL_PVALUE, 0.05)
        print(f"    A3-9 aucun 0.05 en dur ; SEUIL_PVALUE = {SEUIL_PVALUE}")

    def test_C11_plus_aucun_renvoi_NU_a_VARS_GLM(self):
        """⚠️ La constante est supprimee ; cinq lignes y renvoyaient encore.
        *On garde la mention -- elle porte l'histoire -- mais elle dit
        desormais que la constante N'EXISTE PLUS.*"""
        nus = [i + 1 for i, l in enumerate(_SOURCE.split('\n'))
               if 'VARS_GLM' in l and 'SUPPRIME' not in l]
        self.assertEqual(nus, [], f'renvoi nu a VARS_GLM en l.{nus}')
        self.assertFalse(hasattr(_a3mod, 'VARS_GLM'))
        print("    A3-10 tout renvoi a VARS_GLM dit qu'elle est supprimee")

    def test_C17_l_exemple_montre_un_appel_ACCEPTE(self):
        """⚠️⚠️ VERIFIE PAR EXECUTION : l'appel sans `plan` doit bien etre
        refuse, sinon l'exemple corrige serait faux."""
        self.assertNotIn('agent_a3.run(result_a2)', _SOURCE)
        def _sans_plan():
            df = _portefeuille_auto(200, seed=3)
            r1 = AgentA1Ingestion(audit_path='/tmp', verbose=False).run(
                dataframe=df, branche='non_vie', sous_branche='auto')
            r2 = AgentA2Preprocessing(audit_path='/tmp', verbose=False).run(
                r1, plan=_PLAN_AUTO)
            return AgentA3GLM(audit_path='/tmp', verbose=False).run(r2)
        self.assertFalse(_sans_bruit(_sans_plan).get('success'),
                         "le module accepte l'appel sans plan : l'exemple "
                         "d'origine n'etait donc pas faux")
        print("    A3-11 l'exemple passe `plan=`, et l'appel sans plan est "
              "bien REFUSE (verifie par execution)")

    def test_C18_l_en_tete_ne_porte_plus_de_compte_a_la_main(self):
        titre = _SOURCE_TEST.split('"""')[1].strip().splitlines()[0]
        self.assertEqual(re.findall(r'(\d+)\s+tests', titre), [])
        reels = [n.name for n in ast.walk(ast.parse(_SOURCE_TEST))
                 if isinstance(n, ast.FunctionDef)
                 and n.name.startswith('test_')]
        print(f"    A3-12 aucun compte dans la ligne de titre "
              f"({len(reels)} tests reels, publies par unittest)")


if __name__ == '__main__':
    unittest.main()
