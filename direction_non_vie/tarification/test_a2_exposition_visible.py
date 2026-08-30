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

    def test_l_exposition_NON_POSITIVE_est_EXCLUE_et_non_remplacee(self):
        """ETAPE 1b — arbitree par Selasse le 30/08/2026.

        ⚠️⚠️ CE CONTROLE A CHANGE DE CONTENU, ET C'EST DELIBERE. A l'etape 1 il
        epinglait que la MEDIANE etait DITE ; l'etape 1b a tranche la doctrine
        et le geste lui-meme change. *Un controle suit la regle arbitree, il ne
        fige pas un comportement qu'on vient de decider mauvais.*

        ⚠️ Ce n'est pas une doctrine neuve : c'est celle que la couche qualite
        applique depuis toujours sur la meme grandeur -- « IMPOSSIBLE
        MATHEMATIQUEMENT (exposition <= 0) -> regle 1, exclure ». Mesure du
        geste retire : la mediane sous-estimait la frequence de **10,4 %**.
        """
        df = _portefeuille_auto(600, seed=3)
        df.loc[df.index[:60], 'exposition'] = 0.0
        r2 = _a2(df)
        t = _texte(r2)
        self.assertIsNotNone(t)
        self.assertIn('exposition_non_positive_exclue', t)
        self.assertNotIn('mediane', t.lower(),
                         'la mediane est encore appliquee ou annoncee')
        self.assertIn('EXCLUE', t)
        self.assertEqual(len(r2['dataframe']), 540,
                         'les 60 lignes impossibles ne sont pas exclues')
        print(f"    E1-2 exposition <= 0 : 60 lignes EXCLUES, "
              f"{len(r2['dataframe'])} retenues, aucune mediane")

    def test_une_exposition_ABSENTE_est_DECLAREE_et_jamais_inventee(self):
        """ETAPE 1c — arbitree le 30/08/2026 : *lire le plan plutot qu'inventer
        1.0.*

        ⚠️⚠️ CE CONTROLE AUSSI A CHANGE : il epinglait que l'invention etait
        DITE ; elle n'a plus lieu. Le code contredisait sa propre docstring,
        qui explique que sans exposition on obtient « un biais systematique
        pour les contrats partiels » -- puis en inventait une.
        """
        df = _portefeuille_auto(600, seed=3).drop(columns=['exposition'])
        r2 = _a2(df)
        t = _texte(r2)
        self.assertIsNotNone(t)
        self.assertIn('exposition_absente', t)
        self.assertIn('INTROUVABLE', t)
        self.assertIn('AUCUNE exposition n\'a ete inventee', t)
        self.assertIn('SOUS-ESTIME', t,
                      "le motif ne dit pas dans QUEL SENS le tarif se trompe")
        self.assertNotIn('exposition_inventee', t)
        # ⚠️⚠️ ET ON VERIFIE LA DONNEE, PAS SEULEMENT LE TEXTE. Ce controle a
        # ete ELARGI par sa propre violation plantee : reintroduire
        # `df['exposition'] = 1.0` ne le faisait PAS tomber, parce qu'il ne
        # lisait que le message. *Un message qui dit « rien invente » pendant
        # qu'une colonne est inventee, c'est le motif exact de cet audit --
        # dans mon propre filet.*
        self.assertNotIn('exposition', r2['dataframe'].columns,
                         "une colonne d'exposition est CREEE alors que le "
                         "message affirme qu'aucune ne l'a ete")
        print("    E1-3 colonne absente : absence DECLAREE, et la colonne "
              "n'existe NI dans le texte NI dans le dataframe")

    def test_A2_LIT_LE_PLAN_et_trouve_une_colonne_nommee_autrement(self):
        """⚠️⚠️ LE CAS QUI A OUVERT L'ETAPE 1c, ET IL ETAIT VIVANT. A2 cherchait
        la sous-chaine `'exposition'` : `'exposition' in 'exposure'` vaut
        **False**. Sur `auto_fr_reel` -- le seul des 20 plans bati sur le jeu de
        donnees francais reel -- A2 inventait donc 1.0 pour TOUS les contrats
        alors que la vraie colonne etait la, declaree au plan.
        Effet mesure : frequence sous-estimee de **16 %**.
        """
        self.assertFalse('exposition' in 'Exposure'.lower(),
                         'premisse : la sous-chaine ne doit pas trouver '
                         '`Exposure`, sinon ce controle ne prouve rien')
        import dataclasses
        df = _portefeuille_auto(600, seed=3).rename(
            columns={'exposition': 'Exposure'})
        plan = dataclasses.replace(_PLAN_AUTO, exposition='Exposure')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            precedent = logging.root.manager.disable
            logging.disable(logging.CRITICAL)
            try:
                r1 = AgentA1Ingestion(audit_path='/tmp', verbose=False).run(
                    dataframe=df, branche='non_vie', sous_branche='auto')
                r2 = AgentA2Preprocessing(audit_path='/tmp',
                                          verbose=False).run(r1, plan=plan)
            finally:
                logging.disable(precedent)
        self.assertTrue(r2['success'], f"A2 echoue : {r2.get('erreur')}")
        self.assertIsNone(r2.get('rapport_qualite'),
                          "A2 signale quelque chose alors que la colonne "
                          "declaree etait la : il ne l'a pas trouvee")
        print("    E1-3b A2 trouve `Exposure` par le PLAN : rien invente, "
              "rien signale")


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
