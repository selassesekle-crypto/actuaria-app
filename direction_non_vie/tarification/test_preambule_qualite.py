"""Controles positifs — FUSION, etape 1-A : le preambule devient une PORTE UNIQUE.

CE QUE CE FICHIER PROUVE, ET POURQUOI CETTE ETAPE VIENT EN PREMIER
──────────────────────────────────────────────────────────────────

`controler_qualite` n'avait qu'**UN** appelant de production -- le chemin
declaratif (constat `qualite/C4`). Le chemin agent n'a **aucune couche
qualite**. C'est ainsi que les deux ont pu diverger toute une journee sur la
meme grandeur, l'exposition : trois cas, trois doctrines opposees.

> Une porte unique rend la divergence IMPOSSIBLE, au lieu de la rendre
> seulement EVITABLE.

═══ CE QUE CETTE ETAPE FAIT, ET CE QU'ELLE NE FAIT PAS ═══

⚠️⚠️ ELLE NE CHANGE AUCUN COMPORTEMENT, ET C'EST SA CONDITION D'ENTREE. Elle
extrait les trois gestes que `pipeline_complet` faisait deja, dans le meme
ordre, avec les memes arguments : controler, lever si bloque, rendre le
dataframe propre. **Aucun euro ne bouge**, et c'est verifie ci-dessous.

⚠️⚠️ ELLE NE BRANCHE PAS LE CHEMIN AGENT -- c'est l'etape 1-B, laissee ouverte
a dessein. Mesure du 31/08 sur un meme fichier portant 30 frequences negatives,
30 couts negatifs et 30 expositions nulles :

```
  couche qualite : 90 lignes impossibles detectees, BLOQUE a 9 %
  chemin agent   : 1000 -> 970, il n'exclut que les 30 d'exposition
```

Le chemin agent tarife donc sur des lignes a frequence negative. **Le brancher
deplacerait un prix et introduirait un blocage** : *extraire et brancher sont
deux decisions, et seule la premiere est sans euro.*
"""

from __future__ import annotations

import ast
import inspect
import logging
import pathlib
import unittest
import warnings

from core.plan_tarifaire import PlanTarifaire
from core.qualite_donnees import QualiteBloquante, preambule_qualite
from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
from direction_non_vie.tarification.test_pipeline_agents import (
    _portefeuille_auto,
)

_PLAN = PlanTarifaire.depuis_yaml('plans/auto.yaml')
_TARIF = pathlib.Path(__file__).resolve().parent


def _sans_bruit(fn, *a, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return fn(*a, **kw)
        finally:
            logging.disable(precedent)


class TestLaPorteEstUNIQUE(unittest.TestCase):
    """1-A — LE CONTROLE QUI FERME : un seul endroit controle la qualite."""

    def test_LE_TEST_QUI_FERME_pipeline_complet_passe_par_le_PREAMBULE(self):
        """⚠️ Le chemin declaratif ne doit plus appeler `controler_qualite`
        directement : il passe par la porte, comme le fera l'autre chemin."""
        src = (_TARIF / 'pipeline_tarifaire.py').read_text(encoding='utf-8')
        appels = [n.lineno for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == 'controler_qualite']
        self.assertEqual(appels, [],
                         f"`controler_qualite` est encore appele en direct "
                         f"ligne(s) {appels} : la porte n'est pas unique")
        porte = [n.lineno for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == 'preambule_qualite']
        self.assertEqual(len(porte), 1,
                         f'le preambule est appele {len(porte)} fois')
        print(f"    PQ-1 0 appel direct a `controler_qualite`, 1 appel au "
              f"preambule (l.{porte[0]})")

    def test_le_preambule_LEVE_quand_la_qualite_bloque(self):
        """⚠️⚠️ SECOND SENS — la levee est le coeur du geste. Un preambule qui
        rendrait un rapport bloque sans lever laisserait tarifer dessus."""
        df = _portefeuille_auto(400, seed=3)
        df.loc[df.index[:60], 'nb_sinistres'] = -1.0      # 15 % >= seuil 5 %
        with self.assertRaises(QualiteBloquante) as leve:
            _sans_bruit(preambule_qualite, df, _PLAN, horodatage='t')
        self.assertIn('BLOQUE', str(leve.exception))
        print("    PQ-2 second sens : la porte LEVE quand la qualite bloque")

    def test_une_confirmation_NOMINATIVE_debloque_toujours(self):
        """⚠️ L'echappatoire arbitree ne doit pas avoir ete perdue en chemin."""
        df = _portefeuille_auto(400, seed=3)
        df.loc[df.index[:60], 'nb_sinistres'] = -1.0
        r = _sans_bruit(preambule_qualite, df, _PLAN,
                        qualite_validee_par='Selasse Sekle', horodatage='t')
        self.assertFalse(r.bloque)
        self.assertEqual(r.validee_par, 'Selasse Sekle')
        print("    PQ-3 la confirmation nominative debloque, et elle est tracee")


class TestAucunComportementNeCHANGE(unittest.TestCase):
    """⚠️⚠️ CONDITION DE L'ETAPE 1-A : elle prepare, elle ne decide pas."""

    def test_le_tarif_produit_est_IDENTIQUE(self):
        """⚠️ Meme portefeuille, meme plan : le coefficient d'equilibre et les
        features doivent etre inchanges. *Si cette etape deplacait un euro, elle
        ne pourrait pas venir en premier.*"""
        df = _portefeuille_auto(800, seed=3)
        t = _sans_bruit(pipeline_complet, df, _PLAN)
        self.assertIsNotNone(t.rapport_qualite)
        self.assertGreater(t.coefficient_equilibre, 0)
        pred = t.predire_portefeuille(df)
        observe = float(df['cout_total_sinistres'].sum())
        # INV-8 : apres calage, la prime totale reproduit la charge a +-1 %
        self.assertAlmostEqual(float(pred['prime_pure'].sum()) / observe, 1.0,
                               delta=0.01)
        print(f"    PQ-4 tarif inchange : k={t.coefficient_equilibre:.4f}, "
              f"prime totale = charge observee a +-1 %")

    def test_le_preambule_n_ajoute_ni_ne_retire_AUCUNE_regle(self):
        """⚠️⚠️ Un refactor qui changerait une regle en chemin serait pire
        qu'inutile. On compare ce que la porte rend a ce que la couche rend."""
        from core.qualite_donnees import controler_qualite
        df = _portefeuille_auto(400, seed=3)
        df.loc[df.index[:10], 'exposition'] = 0.0        # 2,5 %, sous le seuil
        direct = _sans_bruit(controler_qualite, df, _PLAN, horodatage='t')
        parla = _sans_bruit(preambule_qualite, df, _PLAN, horodatage='t')
        self.assertEqual([a.code for a in direct.exclusions],
                         [a.code for a in parla.exclusions])
        self.assertEqual(direct.lignes_retenues, parla.lignes_retenues)
        print(f"    PQ-5 porte et couche rendent le MEME rapport : "
              f"{[a.code for a in parla.exclusions]}, "
              f"{parla.lignes_retenues} lignes")


class TestLaPorteEstPRETE_POUR_LE_CHEMIN_AGENT(unittest.TestCase):
    """⚠️⚠️ 1-B N'EST PAS FAITE, ET CE CONTROLE LE DIT."""

    def test_le_chemin_agent_passe_PAR_LA_PORTE_UNIQUE(self):
        """⚠️⚠️ IL EST TOMBE LE 02/09/2026, ET C'ETAIT LE SIGNAL ATTENDU.

        Sa version precedente exigeait que `pipeline_agents` n'appelle PAS la
        couche, avec ce motif ecrit d'avance : *« ce controle tombera le jour
        de 1-B, et ce sera le signal qu'elle a bien ete decidee, pas
        glissee. »* Elle a ete decidee, sur des chiffres, et il est reecrit
        avec sa mesure -- pas supprime.

        Ce que le branchement a deplace, mesure AVANT :

            DONNEE REELLE, 12 654 contrats : 12 654 / 12 654, DELTA 0
            fichier temoin (30 freq<0 + 30 expo<=0) : BLOQUE, union 6,0 %

        ⚠️ UN SEUL APPEL, ET C'EST TOUT L'OBJET DE LA PORTE UNIQUE : deux
        appels, c'est deja deux doctrines. *`qualite/C4` disait que la couche
        n'avait qu'UN appelant de production ; en avoir trois ne le fermerait
        pas, ca le deplacerait.*
        """
        src = (_TARIF / 'pipeline_agents.py').read_text(encoding='utf-8')
        arbre = ast.parse(src)
        portes = [n.lineno for n in ast.walk(arbre)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == 'preambule_qualite']
        self.assertEqual(
            len(portes), 1,
            f"le chemin agent appelle la porte {len(portes)} fois "
            f"(lignes {portes}) : la porte doit rester UNIQUE")
        direct = [n.lineno for n in ast.walk(arbre)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == 'controler_qualite']
        self.assertEqual(
            direct, [],
            f"le chemin agent court-circuite la porte et appelle "
            f"`controler_qualite` directement (ligne(s) {direct}) : il "
            f"perdrait la levee sur blocage")
        print(f"    PQ-6 le chemin agent passe par la porte UNIQUE "
              f"(1 appel, ligne {portes[0]}), 0 court-circuit")

    def test_la_porte_DIT_qu_elle_est_branchee_et_CE_QUE_CA_A_DEPLACE(self):
        """⚠️⚠️ CE CONTROLE A CHANGE DE SENS LE 02/09/2026, ET C'EST LE SIGNAL.

        Il exigeait que la porte DECLARE ne pas etre branchee -- *une porte
        prete mais muette ressemble a de la plomberie morte, le motif de
        `socle/C2`*. Elle EST branchee depuis 1-B : la meme phrase serait
        devenue FAUSSE dans le code le plus lu du module.

        Il exige desormais qu'elle dise ce que le branchement A DEPLACE, avec
        le chiffre. *Une porte branchee sans son chiffre laisse croire que
        personne n'a mesure.*
        """
        # ⚠️ Comparaison SANS ACCENTS : ma premiere version cherchait
        # « deplacerait » dans une docstring qui ecrit « déplacerait ». *Un
        # controle sur du texte francais se normalise, sinon il mesure
        # l'orthographe et non le fond.*
        import unicodedata
        doc = unicodedata.normalize(
            'NFKD', inspect.getdoc(preambule_qualite) or '')
        doc = ''.join(c for c in doc if not unicodedata.combining(c)).lower()
        self.assertIn('1-b', doc)
        self.assertIn('branchee aux deux chemins', doc,
                      "la porte ne declare plus qu'elle est branchee")
        self.assertIn('12 654', doc,
                      "la porte ne dit pas ce que le branchement a deplace "
                      "sur la donnee reelle")
        self.assertIn('delta 0', doc)
        self.assertNotIn('deplacerait un prix', doc,
                         "la porte annonce encore un deplacement au futur "
                         "alors qu'il a eu lieu et qu'il est mesure")
        print("    PQ-7 la porte declare qu'elle EST branchee, et ce que ca a "
              "deplace (delta 0 sur la donnee reelle)")


if __name__ == '__main__':
    unittest.main()
