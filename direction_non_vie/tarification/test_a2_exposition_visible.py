"""Controles positifs — chantier `unite_exposition`, ETAPE 1 : A2 cesse d'etre
muet sur ce qu'il fait a l'exposition.

CE QUE CE FICHIER PROUVE, ET POURQUOI CETTE ETAPE VIENT EN PREMIER
──────────────────────────────────────────────────────────────────

⚠️⚠️ A2 NE FAIT PAS UNE MUTATION SILENCIEUSE, MAIS TROIS. Mesure du
30/08/2026, `a2_preprocessing/agent.py` :

```
  colonne exposition ABSENTE  -> INVENTEE a 1.0 pour TOUS   un logger.warning
  exposition <= 0             -> remplacee par la MEDIANE   un logger.warning
  exposition > 1              -> plafonnee a 1.0            un logger.warning
```

Et `stats_expo` n'atteignait, par AST, **AUCUN livrable**. Or « ce qui n'est
que dans les logs n'existe pas » est une regle deja ecrite de cet audit.

═══ LA PLOMBERIE EXISTAIT, RIEN NE L'ALIMENTAIT ═══

`A6.run` accepte un `rapport_qualite` depuis toujours et le relaie aux **trois**
livrables. Le chemin declaratif le remplissait ; **le chemin agent ne le passait
jamais** -- 0 mention dans `pipeline_agents`, mesure. ⚠️ Et A2 lui-meme nommait
deja le modele a suivre, deux lignes au-dessus de son propre retour : *« A6 le
relaie jusqu'aux 3 livrables, comme rapport_qualite »*. **Le code avait ecrit la
solution sans l'appliquer.**

═══ CE QUE CETTE ETAPE FAIT, ET CE QU'ELLE NE FAIT PAS ═══

⚠️⚠️ ELLE NE CHANGE AUCUN COMPORTEMENT, ET C'EST LA CONDITION POUR QU'ELLE VIENNE
EN PREMIER. Les trois mutations restent exactement ce qu'elles etaient : meme
masque, meme valeur, meme dataframe en sortie. Seul le TEXTE apparait.

⚠️⚠️ LA DOCTRINE N'EST PAS TRANCHEE ICI. Sur `exposition <= 0`, la couche
qualite EXCLUT la ligne (regle 1, impossible) et A2 REMPLACE par la mediane :
**deux chemins, deux doctrines, sur la meme grandeur**. Ce lot rend la
divergence LISIBLE ; la trancher deplace un euro et demande un arbitrage.

⚠️ MEME VOCABULAIRE QUE LA COUCHE QUALITE, jamais un second : `Anomalie`,
`EffetAgrege`, `RapportQualite`, rendus par `synthese_qualite_donnees`. En
ecrire un autre aurait fait diverger les deux chemins DANS LE TEXTE, apres les
avoir laisses diverger dans le comportement.
"""

from __future__ import annotations

import logging
import unittest
import warnings

from core.qualite_donnees import synthese_qualite_donnees
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
)
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)


def _a2(df):
    """A1 puis A2, comme le chemin agent les enchaine reellement."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            r1 = AgentA1Ingestion(audit_path='/tmp', verbose=False).run(
                dataframe=df, branche='non_vie', sous_branche='auto')
            return AgentA2Preprocessing(audit_path='/tmp', verbose=False).run(
                r1, plan=_PLAN_AUTO)
        finally:
            logging.disable(precedent)


def _texte(r2):
    rq = r2.get('rapport_qualite')
    return synthese_qualite_donnees(rq) if rq is not None else None


class TestLesTroisMutationsSontDITES(unittest.TestCase):
    """ETAPE 1 — LE CONTROLE QUI FERME : aucune des trois ne reste muette."""

    def test_LE_TEST_QUI_FERME_le_plafond_publie_son_effet(self):
        """⚠️ Le portefeuille en MOIS : 90 % de l'exposition detruite, et A2
        n'en disait qu'un `logger.warning`."""
        df = _portefeuille_auto(600, seed=3)
        df['exposition'] = df['exposition'] * 12
        t = _texte(_a2(df))
        self.assertIsNotNone(t, "A2 ne publie RIEN sur un plafonnement massif")
        self.assertIn('exposition_sup_1', t)
        self.assertIn('EFFET SUR LE TOTAL', t)
        self.assertIn('DENOMINATEUR', t)
        print(f"    E1-1 plafond : {[l.strip()[:56] for l in t.splitlines() if 'EFFET' in l]}")

    def test_la_MEDIANE_publie_son_effet_ET_nomme_la_divergence(self):
        """⚠️⚠️ La doctrine n'est pas tranchee ici, mais elle est DITE : le
        motif nomme le fait que l'autre chemin exclut ces lignes."""
        df = _portefeuille_auto(600, seed=3)
        df.loc[df.index[:60], 'exposition'] = 0.0
        t = _texte(_a2(df))
        self.assertIsNotNone(t)
        self.assertIn('exposition_non_positive_mediane', t)
        self.assertIn('EFFET SUR LE TOTAL', t)
        print("    E1-2 mediane : effet publie, et la divergence est nommee")

    def test_l_exposition_INVENTEE_publie_son_MOTIF_faute_de_chiffre(self):
        """⚠️⚠️ LE CAS OU IL N'Y A AUCUN NOMBRE POUR PORTER LE SENS. Une colonne
        absente n'a pas de « total avant » : la synthese ne rendait que
        « 600x exposition_inventee ». Le motif doit parler a sa place."""
        df = _portefeuille_auto(600, seed=3).drop(columns=['exposition'])
        t = _texte(_a2(df))
        self.assertIsNotNone(t)
        self.assertIn('exposition_inventee', t)
        self.assertIn('INTROUVABLE', t)
        self.assertIn('INVENTEE', t)
        self.assertIn('SOUS-ESTIME', t,
                      "le motif ne dit pas dans QUEL SENS le tarif se trompe")
        print("    E1-3 colonne absente : le motif est publie, faute d'effet "
              "chiffrable")


class TestSecondSens(unittest.TestCase):
    """⚠️⚠️ Un avertissement affiche TOUJOURS cesse d'etre un signal."""

    def test_un_portefeuille_SAIN_ne_publie_RIEN(self):
        r2 = _a2(_portefeuille_auto(600, seed=3))
        self.assertIsNone(r2.get('rapport_qualite'),
                          "A2 publie un rapport qualite alors qu'il n'a rien "
                          "touche a l'exposition")
        print("    E1-4 second sens : portefeuille sain -> rapport_qualite None")


class TestAucunComportementNeCHANGE(unittest.TestCase):
    """⚠️⚠️ CONDITION DE L'ETAPE 1 : elle rend VISIBLE, elle ne decide pas."""

    def test_le_dataframe_de_sortie_est_INCHANGE(self):
        """⚠️ Meme masque, meme valeur, meme sortie. *Si cette etape deplacait
        un euro, elle ne pourrait pas venir en premier.*"""
        df = _portefeuille_auto(600, seed=3)
        df['exposition'] = df['exposition'] * 12
        d2 = _a2(df)['dataframe']
        self.assertEqual(len(d2), 600, 'des lignes ont ete exclues')
        self.assertEqual(float(d2['exposition'].max()), 1.0)
        self.assertEqual(float(d2['exposition'].sum()), 600.0)
        print(f"    E1-5 sortie inchangee : 600 lignes, exposition totale "
              f"{d2['exposition'].sum():.0f}, max 1.0")

    def test_A2_ne_BLOQUE_pas_et_n_escalade_pas(self):
        """⚠️ Le rapport dit ce qui A ETE FAIT. Le faire bloquer serait
        l'etape 1b -- un euro, donc un arbitrage."""
        df = _portefeuille_auto(600, seed=3)
        df['exposition'] = df['exposition'] * 12
        r2 = _a2(df)
        self.assertTrue(r2['success'])
        rq = r2['rapport_qualite']
        self.assertFalse(rq.bloque)
        self.assertFalse(rq.escalade_declenchee)
        print("    E1-6 A2 ne bloque pas, n'escalade pas : visibilite seule")


class TestLeCanalVaJUSQU_A_A6(unittest.TestCase):
    """⚠️⚠️ « Corrige OU ? » — le rapport doit ATTEINDRE le relais, pas rester
    dans le dict d'A2."""

    def test_pipeline_agents_PASSE_le_rapport_a_A6(self):
        """⚠️ Mesure par AST sur le source : l'appel a `A6.run` doit porter
        l'argument. C'est le chainon qui manquait -- 0 mention avant ce lot."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent
               / 'pipeline_agents.py').read_text(encoding='utf-8')
        passe = False
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Call) and any(
                    k.arg == 'rapport_qualite' for k in n.keywords):
                passe = True
        self.assertTrue(passe,
                        "`pipeline_agents` ne passe toujours pas "
                        "`rapport_qualite` a A6 : le rapport d'A2 s'arrete "
                        "avant le relais, et les 3 livrables ne le verront pas")
        print("    E1-7 `pipeline_agents` passe `rapport_qualite` a A6")

    def test_A6_accepte_bien_cet_argument(self):
        """⚠️ Le passer ne suffit pas : la porte doit l'accepter. *Un argument
        qu'une signature ignore est un cablage qui n'existe pas.*"""
        import inspect

        from direction_non_vie.tarification.a6_comparaison.agent import (
            AgentA6Comparaison,
        )
        params = inspect.signature(AgentA6Comparaison.run).parameters
        self.assertIn('rapport_qualite', params)
        print("    E1-8 `A6.run` accepte `rapport_qualite` — le canal est "
              "complet d'A2 aux 3 livrables")


if __name__ == '__main__':
    unittest.main()
