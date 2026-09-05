# -*- coding: utf-8 -*-
"""LE MEME OBJET PUBLIAIT DEUX PRIX POUR LE MEME CONTRAT (lot 2-A).

`TarifNonVie` expose deux surfaces de prix : `tarifer(contrat)`, le livrable
commercial, et `predire_portefeuille(df)`, le chemin vectoriel dont sort le
coefficient d'equilibre. L'en-tete du module annoncait
<< tarifer(contrat) -> reproduit le portefeuille (INV-7) >> et la docstring de
`predire_portefeuille` disait << MEME chemin que tarifer() >>.

⚠️⚠️ MESURE DU 05/09/2026, SUR `auto` A 2 000 LIGNES, 300 CONTRATS :

    299 contrats sur 300 (99,7 %) DIVERGENT de plus d'un centime
    ecart median +39,90 EUR, maximum 402,43 EUR, ratio median 1,1270
    avec `exposition=` fourni : ecart maximum 0,004953 EUR (l'arrondi)

La cause : `predire_portefeuille` prend l'exposition dans la COLONNE du
portefeuille ; `tarifer()`, si l'appelant ne passe rien, retient
`EXPO_ANNUELLE = 1,0`. **Le calcul est identique, seule l'exposition diverge.**

⚠️⚠️ ET AUCUN ORACLE N'EXERCAIT LE CAS QUI DIVERGE. `INV-7a` compare le chemin
vectoriel A LUI-MEME ; `INV-7b` compare bien la paire, mais **en passant
`exposition=float(row["exposition"])`** -- donc dans le seul cas ou elle
s'accorde. *Un oracle qui ne traverse pas le cas ne le couvre pas.*

⚠️⚠️ ET L'ECART N'EST PAS UNE SIMPLE MISE A L'ECHELLE DE DUREE. `a2:845`
derive `kilometrage_annuel / max(exposition, 0,01)`, un PREDICTEUR du GLM :
poser l'exposition a 1,0 change aussi LE PROFIL DE RISQUE presente au modele.
Mesure, 150 contrats par plan :

    `auto` (kilometrage derive) : rapport de duree 1,1420, rapport REEL
                                  1,1538 -- ecart median 0,90 %, jusqu'a
                                  128,11 EUR sur un contrat
    `mrh`, `rcpro`, `flotte_automobile` (aucun facteur derive)
                                : rapport de duree = rapport reel, 0,00 EUR

**Ce lot NE DECIDE PAS laquelle des deux expositions doit primer** -- c'est une
question de produit, rendue a l'actuaire signataire avec ses chiffres. Il rend
l'ecart MESURABLE et DIT. *On rend d'abord visible ; on decide ensuite.*

Ce que cette sentinelle exige :
  DC-1  avec `exposition=` fourni, les deux chemins COINCIDENT au centime ;
  DC-2  ⚠️ sans le parametre, ils DIVERGENT -- le cas qu'aucun oracle
        n'exercait -- et la divergence est DECLAREE (source + phrase) ;
  DC-3  sur un plan SANS facteur derive de l'exposition, l'ecart est
        EXACTEMENT l'effet de duree ;
  DC-4  ⚠️ sur un plan AVEC facteur derive, il ne l'est PAS -- et la condition
        est DERIVEE du portefeuille, jamais codee en dur ;
  DC-5  la phrase publiee ne promet plus un rapport comme s'il etait exact ;
  DC-6  les deux proses du module portent la CONDITION `exposition=`.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""
import inspect
import logging
import os
import sys
import unittest
import warnings

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

import numpy as np
import pandas as pd

from core.conformite_reglementaire import (
    EXPO_DE_L_APPELANT,
    EXPO_SUPPOSEE,
    source_exposition,
)
from core.plan_tarifaire import PlanTarifaire

#: ⚠️ LA COLONNE QUI FAIT LA DIFFERENCE, NOMMEE UNE SEULE FOIS. `a2:845`
#: construit `kilometrage_annuel / max(exposition, 0,01)`. Un plan qui la
#: porte voit l'hypothese d'exposition entrer dans sa matrice de design.
_COLONNE_DERIVEE_DE_L_EXPO = 'kilometrage_annuel'

#: Le centime : l'unite de publication de `tarifer()` (`round(..., 2)`).
_CENTIME = 0.011


def _plan(nom):
    return PlanTarifaire.depuis_yaml(os.path.join(_RACINE, 'plans',
                                                  f'{nom}.yaml'))


class _Socle(unittest.TestCase):
    """Un tarif reel, et les deux surfaces de prix cote a cote."""

    PLAN = 'auto'
    N = 1500

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)
        from direction_non_vie.tarification import test_plan_invariants as T
        from direction_non_vie.tarification.pipeline_tarifaire import (
            pipeline_complet,
        )
        generateurs = {'auto': T.portefeuille_auto, 'mrh': T.portefeuille_mrh,
                       'rcpro': T.portefeuille_rcpro}
        np.random.seed(7)
        cls.plan = _plan(cls.PLAN)
        cls.df = generateurs[cls.PLAN](cls.N, 1)
        cls.tarif = pipeline_complet(cls.df, cls.plan)
        cls.vect = cls.tarif.predire_portefeuille(cls.df)
        cls.expo = pd.to_numeric(cls.df[cls.plan.exposition], errors='coerce')
        # ⚠️ La condition est DERIVEE du portefeuille, pas ecrite en dur :
        # un plan qui gagnerait ou perdrait la colonne serait suivi.
        cls.derive_de_l_expo = _COLONNE_DERIVEE_DE_L_EXPO in cls.df.columns

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def _contrats(self, n=120):
        for i in self.df.index[:n]:
            e = float(self.expo.loc[i])
            v = float(self.vect.loc[i, 'prime_pure'])
            if e <= 0 or v <= 0:
                continue
            yield self.df.loc[i].to_dict(), e, v


class TestAutoDeuxChemins(_Socle):
    """⚠️ `auto` PORTE `kilometrage_annuel` : c'est le plan ou l'hypothese
    d'exposition entre AUSSI dans la matrice de design."""

    PLAN = 'auto'

    def test_DC0_la_fixture_traverse_bien_le_cas(self):
        """⚠️⚠️ *Une fixture doit prouver qu'elle traverse le chemin qu'elle
        mesure.* Sans expositions infra-annuelles, tout ce fichier serait vert
        sans rien avoir mesure."""
        self.assertTrue(self.derive_de_l_expo,
                        f'`{_COLONNE_DERIVEE_DE_L_EXPO}` a disparu du '
                        f'portefeuille `auto` : DC-4 ne prouve plus rien')
        infra = float((self.expo < 1.0).mean())
        self.assertGreater(infra, 0.5,
                           f'seulement {infra:.1%} de contrats infra-annuels : '
                           f'la divergence ne peut pas se mesurer')

    def test_DC1_avec_exposition_fournie_les_deux_chemins_COINCIDENT(self):
        """⚠️ Le second sens, et c'est lui qui prouve que le calcul est bien
        le MEME : quand l'appelant fournit la duree, l'ecart retombe a
        l'arrondi au centime."""
        pire = 0.0
        for contrat, e, v in self._contrats():
            r = self.tarif.tarifer(contrat, exposition=e)
            self.assertTrue(r['success'])
            self.assertEqual(r['exposition_source'], EXPO_DE_L_APPELANT)
            pire = max(pire, abs(float(r['prime_pure']) - v))
        self.assertLess(
            pire, _CENTIME,
            f'avec `exposition=` fourni, les deux chemins divergent encore de '
            f'{pire:.4f} EUR : ce n est plus un arrondi, c est un calcul '
            f'different')

    def test_DC2_SANS_le_parametre_ils_DIVERGENT_et_c_est_DECLARE(self):
        """⚠️⚠️ LE CAS QU'AUCUN ORACLE N'EXERCAIT. `INV-7b` passe toujours
        `exposition=` ; personne ne regardait ce qui se passe sans."""
        divergents, phrases = 0, 0
        for contrat, _, v in self._contrats():
            r = self.tarif.tarifer(contrat)
            self.assertTrue(r['success'])
            # ⚠️ L'hypothese est DECLAREE : source ET phrase, pas l'une sans
            # l'autre. *Un prix suppose qui ne se dit pas est un prix faux.*
            self.assertEqual(r['exposition_source'], EXPO_SUPPOSEE)
            self.assertEqual(float(r['exposition_retenue']), 1.0)
            if r.get('exposition_hypothese'):
                phrases += 1
            if abs(float(r['prime_pure']) - v) > _CENTIME:
                divergents += 1
        self.assertGreater(
            divergents, 0,
            "sans `exposition=`, les deux chemins ne divergent plus : soit le "
            "defaut a change, soit la fixture ne porte plus de contrat "
            "infra-annuel -- dans les deux cas ce fichier ne mesure plus rien")
        self.assertEqual(
            phrases, divergents,
            f'{divergents} contrats divergent mais seulement {phrases} '
            f'portent une phrase : un ecart de prix reste MUET')

    def test_DC4_l_ecart_DEPASSE_l_effet_de_duree_quand_un_facteur_en_derive(
            self):
        """⚠️⚠️ LE POINT QUE LA PHRASE PROMETTAIT A TORT. `a2:845` derive
        `kilometrage_annuel / max(exposition, 0,01)` : poser l'exposition a 1,0
        change le PROFIL DE RISQUE, pas seulement la duree facturee. L'ecart
        n'est donc pas `prime / exposition`."""
        self.assertTrue(self.derive_de_l_expo)
        pire = 0.0
        for contrat, e, v in self._contrats():
            r = self.tarif.tarifer(contrat)
            pire = max(pire, abs(float(r['prime_pure']) - v / e))
        self.assertGreater(
            pire, _CENTIME,
            "sur un plan qui derive un facteur de l'exposition, l'ecart se "
            "reduit a la seule mise a l'echelle de duree : soit `a2` ne derive "
            "plus le kilometrage, soit ce facteur est sorti du modele -- la "
            "phrase publiee et les docstrings disent le contraire et doivent "
            "etre relues")


class TestMrhDeuxChemins(_Socle):
    """⚠️ L'ASYMETRIE ENTRE VOISINS : `mrh` ne porte AUCUN facteur derive de
    l'exposition. C'est le temoin -- sans lui, DC-4 pourrait passer pour une
    propriete du code plutot que du plan."""

    PLAN = 'mrh'

    def test_DC3_sans_facteur_derive_l_ecart_est_EXACTEMENT_la_duree(self):
        self.assertFalse(
            self.derive_de_l_expo,
            f'`mrh` porte desormais `{_COLONNE_DERIVEE_DE_L_EXPO}` : ce '
            f'temoin ne temoigne plus de rien')
        pire = 0.0
        for contrat, e, v in self._contrats():
            r = self.tarif.tarifer(contrat)
            pire = max(pire, abs(float(r['prime_pure']) - v / e))
        self.assertLess(
            pire, _CENTIME,
            f'sans facteur derive, l ecart devrait etre EXACTEMENT la mise a '
            f'l echelle de duree ; il vaut {pire:.4f} EUR')

    def test_DC1b_avec_exposition_fournie_ils_COINCIDENT_aussi_ici(self):
        pire = 0.0
        for contrat, e, v in self._contrats():
            r = self.tarif.tarifer(contrat, exposition=e)
            pire = max(pire, abs(float(r['prime_pure']) - v))
        self.assertLess(pire, _CENTIME)


class TestCeQueLesTextesPROMETTENT(unittest.TestCase):
    """⚠️⚠️ *Le TEXTE qui accompagne un comportement se relit quand il
    change.* Trois proses affirmaient l'equivalence sans sa condition."""

    def test_DC5_la_phrase_publiee_ne_promet_plus_un_rapport_EXACT(self):
        """Elle annoncait << rapport {1/expo} >> comme si l'ecart etait une
        pure mise a l'echelle. Mesure : faux sur `auto`."""
        _, source, phrase = source_exposition(0.5, None)
        self.assertEqual(source, EXPO_SUPPOSEE)
        self.assertIsNotNone(phrase)
        # ⚠️ On garde le mot que `EX-*` verrouille deja.
        self.assertIn('IGNOREE', phrase)
        self.assertIn("L'effet de DUREE seul", phrase)
        for attendu in ("PAS forcement le rapport total", 'derive un facteur',
                        'profil de risque'):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, phrase)

    def test_DC6_les_proses_du_module_portent_la_CONDITION(self):
        """⚠️ L'en-tete du module et la docstring de `predire_portefeuille`
        annonçaient l'equivalence SANS condition."""
        from direction_non_vie.tarification import pipeline_tarifaire as P
        entete = inspect.getdoc(P) or ''
        self.assertIn('tarifer(contrat, exposition=', entete,
                      "l en-tete annonce encore que `tarifer(contrat)` "
                      "reproduit le portefeuille sans sa condition")
        self.assertIn('SOUS CONDITION', entete)
        doc = inspect.getdoc(P.TarifNonVie.predire_portefeuille) or ''
        self.assertNotIn('MÊME chemin que\n        `tarifer()`', doc)
        for attendu in ('pas la même exposition', 'INV-7b',
                        'kilometrage_annuel'):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, doc)

    def test_DC6b_le_chiffre_de_C7_porte_desormais_sa_condition(self):
        """⚠️ Le `0,0036 EUR` du constat `pipeline/C7` est vrai AVEC
        `exposition=` fourni, et faux sans. Il a besoin de sa condition."""
        from direction_non_vie.tarification import pipeline_tarifaire as P
        doc = inspect.getdoc(P.TarifNonVie.predire_portefeuille) or ''
        i = doc.find('0,0036')
        self.assertGreater(i, 0, 'le chiffre de C7 a disparu de la docstring')
        self.assertIn('exposition=', doc[i:i + 400],
                      "le `0,0036 EUR` est publie sans dire qu'il vaut "
                      "seulement quand l exposition est fournie")


if __name__ == '__main__':
    unittest.main(verbosity=2)
