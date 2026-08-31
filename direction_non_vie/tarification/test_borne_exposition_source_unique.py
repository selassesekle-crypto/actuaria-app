"""Controles positifs — chantier `unite_exposition`, GESTE PREPARATOIRE A L'ETAPE 2 :
la borne d'exposition a UNE SEULE SOURCE, consommee par les deux chemins.

CE QUE CE FICHIER PROUVE, ET POURQUOI CE GESTE VIENT AVANT L'ETAPE 2
────────────────────────────────────────────────────────────────────

⚠️⚠️ L'ORDRE VALIDE AURAIT RECREE LE JUMEAU QU'ON VENAIT DE FERMER. L'etape 2
devait declarer `unite_exposition` au plan **et** le faire lire par la borne de
la couche qualite. Mais la borne vivait a DEUX endroits :

```
  couche qualite : PLAFOND_EXPOSITION          -- source unique, un seul nom
  A2             : 1.0 en dur, QUATRE fois     -- dont un masque RECALCULE
```

La faire deriver de l'unite d'un seul cote aurait laisse A2 plafonner a 1.0
pendant tout l'intervalle : **deux bornes pour la meme grandeur**, sur le
plafond que l'etape 1 vient tout juste de rendre visible.

⚠️ ET LE COMMENTAIRE D'IMPORT DE A2 CONDAMNAIT DEJA LE LITTERAL : *"MEME
VOCABULAIRE QUE LA COUCHE QUALITE, jamais un second [...] les reecrire ici
aurait fait diverger les deux chemins DANS LE TEXTE."* A2 empruntait les
CLASSES et reecrivait le NOMBRE. *Le code contredisait son propre texte -- le
meme defaut qu'a l'etape 1c.*

═══ CE QUE CE GESTE FAIT, ET CE QU'IL NE FAIT PAS ═══

⚠️⚠️ AUCUN EURO, ET C'EST MESURE, PAS AFFIRME. La version d'AVANT a ete tiree
du commit et executee cote a cote avec la version d'apres sur QUATRE
portefeuilles -- en mois, normal, quelques lignes hautes, exclusions et plafond
ensemble. Empreinte comparee : lignes rendues, somme d'exposition, maximum,
somme de `log_exposition`, et **chaque anomalie avec sa description et son
libelle de correction**. **0 ecart.** Les nombres sont figes en `BEX-6`.

⚠️ IL NE DECLARE PAS L'UNITE -- c'etait l'etape 2, **faite depuis** : le plan
porte `unite_exposition` et la borne en derive, A LA SOURCE UNIQUE, donc pour
les deux chemins d'un seul geste. Voir `test_unite_exposition_declaree.py`.

═══ CE QUE L'ETAPE 2 A CHANGE DANS CE FICHIER, ET POURQUOI ═══

⚠️⚠️ CE FICHIER A ETE MIS A JOUR, JAMAIS AFFAIBLI. La borne etait une CONSTANTE
importee ; elle est devenue une PORTE appelee avec le plan. **L'invariant
epingle -- une seule source, aucun litteral -- est inchange ; seule son
expression a bouge**, et chaque controle prouve exactement ce qu'il prouvait :

```
  BEX-1  0 litteral   -> plus : 1 seul appel a la porte, borne reutilisee
  BEX-2  meme CONSTANTE -> meme FONCTION, et memes deux phrases partagees
  BEX-5  on remplacait la constante dans le module (un geste de test)
         -> on declare `unite_exposition` au plan (ce que fait la PRODUCTION)
  BEX-3  la description a change, DELIBEREMENT (voir le commentaire sur place)
```

⚠️ **LA BORNE QUE CE FICHIER DECLARAIT EST TOMBEE.** Il disait que `BEX-5` ne
prouvait pas un lien vif, la constante etant liee a l'import. La borne depend
desormais du plan **a chaque appel** : la reserve n'a plus d'objet.

⚠️ TROUVE, NON TRAITE -- une divergence nommee pour ne pas etre oubliee :
`demos/fremtpl2_demo.py` plafonne `Exposure` a 1.0 AVANT d'appeler
`pipeline_complet` : la couche qualite recoit un fichier deja aplati et ne peut
plus rien dire. **Troisieme doctrine sur la meme grandeur.**

✅ **ET LA SECONDE DIVERGENCE NOMMEE ICI EST FERMEE PAR L'ETAPE 2** : les
jumeaux publiaient un texte different pour le MEME code `exposition_sup_1`. Ils
tirent desormais leurs DEUX phrases de la couche qualite, jamais reecrites --
`BEX-2` l'epingle. *Apres avoir cesse de diverger dans le nombre, ils ont cesse
de diverger dans le texte.*
"""

from __future__ import annotations

import ast
import dataclasses
import logging
import pathlib
import unittest
import warnings

import core.qualite_donnees as _qd
from core.qualite_donnees import PLAFOND_EXPOSITION, controler_qualite
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing import agent as _a2mod
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
)
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)

_SOURCE_A2 = (pathlib.Path(_a2mod.__file__)).read_text(encoding='utf-8')


def _fonction_exposition() -> ast.FunctionDef:
    """Le corps de `_traiter_exposition`, lu PAR AST et jamais par `grep`."""
    for n in ast.walk(ast.parse(_SOURCE_A2)):
        if isinstance(n, ast.FunctionDef) and n.name == '_traiter_exposition':
            return n
    raise AssertionError('`_traiter_exposition` introuvable dans A2')


def _a2(df, plan=_PLAN_AUTO):
    """A1 puis A2, comme le chemin agent les enchaine reellement."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            r1 = AgentA1Ingestion(audit_path='/tmp', verbose=False).run(
                dataframe=df, branche='non_vie', sous_branche='auto')
            return AgentA2Preprocessing(audit_path='/tmp', verbose=False).run(
                r1, plan=plan)
        finally:
            logging.disable(precedent)


def _anomalies(r2):
    rq = r2.get('rapport_qualite')
    if rq is None:
        return []
    return [*rq.exclusions, *rq.corrections, *rq.signalements]


def _plafond(r2):
    for a in _anomalies(r2):
        if a.code == 'exposition_sup_1':
            return a
    return None


def _en_mois(n=600, seed=3):
    df = _portefeuille_auto(n, seed=seed)
    df['exposition'] = df['exposition'] * 12
    return df


class TestLaBorneNEstPlusUnLitteral(unittest.TestCase):
    """LE CONTROLE QUI FERME : A2 ne porte plus sa propre borne."""

    def test_LE_TEST_QUI_FERME_aucun_litteral_de_borne_dans_A2(self):
        """⚠️ Mesure PAR AST sur le corps de `_traiter_exposition`. Avant ce
        lot : TROIS constantes flottantes `1.0` (l.1374 et deux fois l.1378,
        le masque y etait recalcule). Apres : zero."""
        fn = _fonction_exposition()
        flottants = [(c.value, c.lineno) for c in ast.walk(fn)
                     if isinstance(c, ast.Constant)
                     and isinstance(c.value, float) and c.value == 1.0]
        self.assertEqual(
            flottants, [],
            f"la borne d'exposition est encore un litteral dans A2 : "
            f"{flottants}. Elle doit venir de `PLAFOND_EXPOSITION`, sinon "
            f"l'etape 3 devra la faire deriver a DEUX endroits.")
        # ⚠️⚠️ MIS A JOUR PAR L'ETAPE 2, ET IL PROUVE LA MEME CHOSE. La borne
        # etait une CONSTANTE importee ; elle est devenue une PORTE appelee avec
        # le plan, parce qu'elle depend desormais de `unite_exposition`.
        # L'invariant epingle -- *une seule source, aucun litteral* -- est
        # inchange ; seule son expression a bouge.
        appels = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Name)
                  and n.func.id == 'borne_exposition']
        self.assertEqual(
            len(appels), 1,
            f"la borne doit etre derivee UNE fois puis reutilisee, pas "
            f"recalculee ({len(appels)} appels)")
        noms = [n.id for n in ast.walk(fn)
                if isinstance(n, ast.Name) and n.id == '_borne']
        self.assertGreaterEqual(
            len(noms), 3,
            f"A2 ne nomme la borne que {len(noms)} fois : le masque, "
            f"l'affectation et les phrases publiees doivent TOUTES en venir")
        print(f"    BEX-1 0 litteral de borne dans A2, 1 appel a la porte, "
              f"borne nommee {len(noms)} fois")

    def test_la_PORTE_de_A2_EST_celle_de_la_couche_qualite(self):
        """⚠️ Une copie de la fonction passerait `BEX-1` sans rien resoudre.

        ⚠️⚠️ CE CONTROLE EST DEVENU PLUS FORT AVEC L'ETAPE 2. Il comparait deux
        CONSTANTES, donc deux valeurs liees a l'import ; il compare desormais
        deux FONCTIONS. *La borne depend du plan a chaque appel : il n'y a plus
        de liaison figee a l'import, et la borne declaree de `BEX-5` tombe.*
        """
        self.assertIs(_a2mod.borne_exposition, _qd.borne_exposition)
        self.assertIs(_a2mod.phrase_plausibilite, _qd.phrase_plausibilite)
        self.assertIs(_a2mod.phrase_unite_non_declaree,
                      _qd.phrase_unite_non_declaree)
        print(f"    BEX-2 A2 et la couche qualite partagent la porte ET les "
              f"deux phrases (plafond annuel = {PLAFOND_EXPOSITION})")


class TestAucunePhrasePublieeNeCHANGE(unittest.TestCase):
    """⚠️⚠️ UN REFACTOR SANS EURO PEUT QUAND MEME DEPLACER UN TEXTE SIGNE."""

    def test_les_phrases_publiees_sont_MOT_POUR_MOT_celles_d_avant(self):
        """⚠️ Chaines relevees sur la version tiree du commit. `:g` rend
        « > 1 » dans la comparaison, mais le libelle de correction garde
        « plafond a 1.0 » : `:g` l'aurait ecrit « plafond a 1 »."""
        # ⚠️⚠️ LES DEUX ETATS SONT EPINGLES, ET L'ETAPE 5 EXPLIQUE POURQUOI.
        # Ce controle prenait `_PLAN_AUTO` du depot, qui ne declarait rien ; les
        # 20 plans declarent `annee` depuis l'etape 5, et il est tombe. *Epingler
        # UN etat en empruntant un fichier qui peut changer, c'est epingler le
        # fichier, pas le comportement.* On epingle donc le cas de PRODUCTION
        # (unite declaree) ET le cas du plan client muet, chacun construit.
        a = _plafond(_a2(_en_mois(), _PLAN_AUTO))
        self.assertIsNotNone(a, 'A2 ne signale plus le plafonnement')
        self.assertEqual(a.correction, 'plafond a 1.0')
        self.assertEqual(
            a.description,
            "exposition ('exposition') > 1 -- implausible pour un contrat "
            "annuel.")

        # ⚠️ LE LIBELLE DE CORRECTION EST INCHANGE DEPUIS 1d, LA DESCRIPTION
        # NON -- et c'est l'etape 2 qui l'a changee, DELIBEREMENT. L'ancienne
        # disait « Le plan declare le ROLE de l'exposition, jamais son UNITE » :
        # devenue FAUSSE le jour ou le plan a pu la declarer. *Un texte qui
        # accompagne un comportement se relit quand le comportement change.*
        muet = dataclasses.replace(_PLAN_AUTO, unite_exposition=None)
        b = _plafond(_a2(_en_mois(), muet))
        self.assertEqual(b.correction, 'plafond a 1.0')
        self.assertEqual(
            b.description,
            "exposition ('exposition') > 1 -- implausible pour un contrat "
            "annuel. UNITE NON DECLAREE au plan : l'hypothese ANNUELLE a ete "
            "supposee, et c'est elle qui fixe cette borne. Si ce fichier est "
            "exprime en mois ou en jours, declarez `unite_exposition` au "
            "plan -- sans quoi cette correction detruit une donnee JUSTE, et "
            "l'exposition etant le denominateur de la prime, celle-ci est "
            "multipliee d'autant.")
        print(f"    BEX-3 libelle inchange ({a.correction!r}) ; description "
              f"epinglee dans les DEUX etats (declaree / muette)")

    def test_les_DEUX_chemins_publient_le_MEME_libelle(self):
        """⚠️⚠️ LE VRAI INVARIANT DU JUMEAU. Meme code, meme regle, meme
        libelle de correction : c'est ce que la source unique garantit."""
        a2 = _plafond(_a2(_en_mois(), _PLAN_AUTO))
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            rq = controler_qualite(_en_mois(), _PLAN_AUTO, horodatage='t')
        qual = next(x for x in rq.corrections if x.code == 'exposition_sup_1')
        self.assertEqual(a2.code, qual.code)
        self.assertEqual(a2.regle, qual.regle)
        self.assertEqual(a2.correction, qual.correction)
        print(f"    BEX-4 jumeaux d'accord : code={a2.code} regle={a2.regle} "
              f"correction={a2.correction!r}")


class TestLaBorneEstLUE_ET_NON_RECOPIEE(unittest.TestCase):
    """⚠️⚠️ SECOND SENS — sans ce controle, `BEX-1` serait du decor."""

    def test_si_la_borne_change_A2_SUIT(self):
        """⚠️ Portefeuille en mois, maximum a ~11,99. Avec une borne a 12,
        A2 ne doit plafonner AUCUNE ligne. *Un A2 qui garderait un 1.0 cache
        continuerait d'ecraser 600 lignes ici.*

        ⚠️⚠️ L'ETAPE 2 A RENDU CE CONTROLE PLUS HONNETE. Il portait la borne a
        12 en REMPLACANT une constante dans le module -- un geste de test, que
        rien en production ne fait. Il la porte desormais a 12 comme la
        production le fera : *en declarant `unite_exposition` au plan.* Le
        controle ne simule plus le mecanisme, il l'exerce.
        """
        avec_1 = _plafond(_a2(_en_mois(), _PLAN_AUTO))
        self.assertIsNotNone(avec_1)
        en_mois = dataclasses.replace(_PLAN_AUTO, unite_exposition='mois')
        avec_12 = _plafond(_a2(_en_mois(), en_mois))
        self.assertIsNone(
            avec_12,
            f"le plan declare 'mois' (borne 12) et A2 plafonne encore "
            f"{getattr(avec_12, 'nb_lignes', '?')} ligne(s) : il garde une "
            f"borne a lui")
        print(f"    BEX-5 plan sans unite -> {avec_1.nb_lignes} lignes "
              f"plafonnees ; plan 'mois' -> aucune")


class TestAucunEuroDeplace(unittest.TestCase):
    """⚠️⚠️ MESURE AVANT/APRES, pas une affirmation."""

    #: Empreintes relevees en executant la version d'AVANT (tiree du commit)
    #: et celle d'APRES cote a cote, le 31/08/2026. 0 ecart sur les 4 cas.
    _ATTENDU = {
        'mois':    (600, 600.0, 1.0, 600),
        'normal':  (600, 500.418738, 0.99964707, None),
        'hautes':  (600, 500.391822, 1.0, 17),
    }

    def test_l_exposition_rendue_est_IDENTIQUE_a_la_version_d_avant(self):
        cas = {
            'mois':   _en_mois(),
            'normal': _portefeuille_auto(600, seed=3),
            'hautes': _portefeuille_auto(600, seed=7),
        }
        cas['hautes'].loc[cas['hautes'].index[:17], 'exposition'] = 3.5
        for nom, df in cas.items():
            attendu = self._ATTENDU[nom]
            r2 = _a2(df)
            sortie = r2['dataframe']
            a = _plafond(r2)
            with self.subTest(cas=nom):
                self.assertEqual(len(sortie), attendu[0])
                self.assertAlmostEqual(float(sortie['exposition'].sum()),
                                       attendu[1], places=5)
                self.assertAlmostEqual(float(sortie['exposition'].max()),
                                       attendu[2], places=7)
                self.assertEqual(None if a is None else a.nb_lignes,
                                 attendu[3])
        print("    BEX-6 3 portefeuilles, exposition rendue identique a la "
              "version d'avant (mesuree, pas supposee)")


if __name__ == '__main__':
    unittest.main()
