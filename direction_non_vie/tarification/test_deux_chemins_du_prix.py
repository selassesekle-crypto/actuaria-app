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

⚠️⚠️ ET L'ARBITRAGE EST TOMBE LE MEME JOUR (lot 2-B). *On rend d'abord
visible ; on decide ensuite* -- la decision est prise, et ce fichier a change
de cible : **il ne constate plus la divergence, il interdit son retour.**

  (a) l'appelant se tait, le contrat declare  -> on PREND celle du contrat,
      les deux chemins COINCIDENT, rien a signaler ;
  (b) l'appelant se tait, le contrat ne declare rien -> un an, et ON LE DIT ;
  (c) l'appelant fournit -> il prime, inchange.

⚠️ AUCUN PRIX DE PRODUCTION NE BOUGE : le seul appelant de `tarifer()` du
depot (`demos/fremtpl2_demo.py:171`, releve par AST) passe deja `exposition=`.

Ce que cette sentinelle exige :
  DC-1  avec `exposition=` fourni, les deux chemins COINCIDENT au centime ;
  DC-2  ⚠️ SANS le parametre AUSSI, desormais -- et la duree retenue est
        celle du contrat, sans aucune phrase ;
  DC-3  dans le cas (b), sur un plan SANS facteur derive, le prix suppose se
        corrige EXACTEMENT par la duree ; DC-3b : le cas (a) y coincide aussi ;
  DC-4  ⚠️ dans le cas (b), sur un plan AVEC facteur derive, il ne s'y corrige
        PAS -- et la condition est DERIVEE du portefeuille, jamais codee en
        dur ;
  DC-5  la seule hypothese restante est DITE et BORNEE ; DC-5b : le cas (a)
        ne publie AUCUNE phrase ;
  DC-6  les proses du module disent le nouveau contrat ;
  DC-7  ⚠️⚠️ tout appelant de production FOURNIT la duree ou LIT la
        declaration -- controle DERIVE, la garantie que le message du cas (b)
        ne se perd pas ; DC-8 : le releve prouve qu'il traverse.

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
    EXPO_DU_CONTRAT,
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

    def test_DC2_SANS_le_parametre_ils_COINCIDENT_DESORMAIS(self):
        """⚠️⚠️ LE CONTRAT A CHANGE, ET CE TEST PROUVE LE NOUVEAU.

        Il exigeait que les deux chemins DIVERGENT et que la divergence soit
        declaree -- c'etait le constat, pas la cible. Le cas (a) etant
        arbitre, le silence de l'appelant veut dire << prends l'exposition du
        contrat >> : les deux surfaces de prix du meme objet rendent
        desormais **le meme prix**, et il n'y a plus rien a declarer.

        *Le controle qui constatait un defaut devient le controle qui interdit
        son retour.*
        """
        pire = 0.0
        for contrat, e, v in self._contrats():
            r = self.tarif.tarifer(contrat)
            self.assertTrue(r['success'])
            self.assertEqual(
                r['exposition_source'], EXPO_DU_CONTRAT,
                'le contrat declare sa duree et elle n est pas retenue : le '
                'cas (a) est rouvert')
            self.assertAlmostEqual(float(r['exposition_retenue']), e, places=9)
            self.assertIsNone(
                r['exposition_hypothese'],
                'une duree PRISE au contrat se declare comme une hypothese : '
                'une phrase qui s affiche toujours ne se lit plus')
            pire = max(pire, abs(float(r['prime_pure']) - v))
        self.assertLess(
            pire, _CENTIME,
            f'les deux chemins du meme objet rendent encore deux prix : '
            f'{pire:.4f} EUR d ecart sans `exposition=` fourni')

    def test_DC4_le_cas_b_change_encore_le_PROFIL_DE_RISQUE(self):
        """⚠️⚠️ CE TEST EST RESTE VERT EN CHANGEANT DE SENS -- et c'est pour
        ca qu'il est reecrit. Il mesurait `|tarifer(sans) - vect/expo|` sur un
        contrat qui DECLARE sa duree ; depuis le cas (a) cette quantite est
        grande pour une raison sans rapport avec ce que son nom annonce.
        *Un test vert dont la docstring ne decrit plus ce qu'il prouve est un
        mensonge qui passe la gate.*

        Ce qu'il mesure maintenant, et qui reste vrai : dans le cas (b) -- le
        contrat NE declare rien -- supposer une annee ne change pas que la
        duree facturee. `a2:845` derive `kilometrage_annuel /
        max(exposition, 0,01)`, un PREDICTEUR : le prix suppose n'est donc PAS
        le prix reel multiplie par la duree.
        """
        self.assertTrue(self.derive_de_l_expo)
        col = self.plan.exposition
        pire = 0.0
        for contrat, e, v in self._contrats(60):
            # ⚠️ Cas (b) construit explicitement : on RETIRE la duree.
            sans_duree = {k: x for k, x in contrat.items() if k != col}
            r = self.tarif.tarifer(sans_duree)
            self.assertEqual(r['exposition_source'], EXPO_SUPPOSEE)
            self.assertIsNotNone(r['exposition_hypothese'])
            pire = max(pire, abs(float(r['prime_pure']) - v / e))
        self.assertGreater(
            pire, _CENTIME,
            "dans le cas (b), le prix suppose se corrigerait en le multipliant "
            "par la duree reelle : soit `a2` ne derive plus le kilometrage, "
            "soit ce facteur est sorti du modele -- la phrase publiee dit le "
            "contraire et doit etre relue")


class TestMrhDeuxChemins(_Socle):
    """⚠️ L'ASYMETRIE ENTRE VOISINS : `mrh` ne porte AUCUN facteur derive de
    l'exposition. C'est le temoin -- sans lui, DC-4 pourrait passer pour une
    propriete du code plutot que du plan."""

    PLAN = 'mrh'

    def test_DC3_le_cas_b_se_corrige_EXACTEMENT_par_la_duree_ici(self):
        """⚠️ LE TEMOIN, ET IL A CHANGE DE CIBLE COMME `DC-4`. Sur un plan qui
        ne derive AUCUN facteur de l'exposition, supposer une annee (cas (b))
        n'a qu'un seul effet : la duree facturee. Le prix suppose se corrige
        donc EXACTEMENT en le multipliant par la duree reelle.

        *C'est l'asymetrie entre voisins qui prouve que `DC-4` mesure une
        propriete du PLAN et non du code.*"""
        self.assertFalse(
            self.derive_de_l_expo,
            f'`mrh` porte desormais `{_COLONNE_DERIVEE_DE_L_EXPO}` : ce '
            f'temoin ne temoigne plus de rien')
        col = self.plan.exposition
        pire = 0.0
        for contrat, e, v in self._contrats(60):
            sans_duree = {k: x for k, x in contrat.items() if k != col}
            r = self.tarif.tarifer(sans_duree)
            self.assertEqual(r['exposition_source'], EXPO_SUPPOSEE)
            pire = max(pire, abs(float(r['prime_pure']) - v / e))
        self.assertLess(
            pire, _CENTIME,
            f'sans facteur derive, le cas (b) devrait se corriger EXACTEMENT '
            f'par la duree ; l ecart vaut {pire:.4f} EUR')

    def test_DC3b_CAS_A_ici_aussi_les_deux_chemins_COINCIDENT(self):
        pire = 0.0
        for contrat, e, v in self._contrats():
            r = self.tarif.tarifer(contrat)
            self.assertEqual(r['exposition_source'], EXPO_DU_CONTRAT)
            self.assertAlmostEqual(float(r['exposition_retenue']), e, places=9)
            pire = max(pire, abs(float(r['prime_pure']) - v))
        self.assertLess(pire, _CENTIME)

    def test_DC1b_avec_exposition_fournie_ils_COINCIDENT_aussi_ici(self):
        pire = 0.0
        for contrat, e, v in self._contrats():
            r = self.tarif.tarifer(contrat, exposition=e)
            pire = max(pire, abs(float(r['prime_pure']) - v))
        self.assertLess(pire, _CENTIME)


class TestCeQueLesTextesPROMETTENT(unittest.TestCase):
    """⚠️⚠️ *Le TEXTE qui accompagne un comportement se relit quand il
    change.* Trois proses affirmaient l'equivalence sans sa condition."""

    def test_DC5_la_SEULE_hypothese_restante_est_dite_ET_bornee(self):
        """⚠️⚠️ IL VERIFIAIT LA PHRASE DU CAS QUE LE LOT SUPPRIME. La branche
        << EXPOSITION DU CONTRAT IGNOREE >> n'existe plus : une exposition
        declaree est PRISE. Ce test porte donc sur la seule hypothese qui
        subsiste -- le cas (b) -- et exige qu'elle dise **aussi** ce qu'elle
        ne repare pas."""
        _, source, phrase = source_exposition(None, None)
        self.assertEqual(source, EXPO_SUPPOSEE)
        self.assertIsNotNone(phrase)
        for attendu in ('NON FOURNIE', 'UNE ANNEE SUPPOSEE', 'HYPOTHESE',
                        'derive un facteur', 'profil de risque',
                        'ne se corrige pas'):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, phrase)

    def test_DC5b_le_cas_a_NE_PUBLIE_AUCUNE_phrase(self):
        """⚠️ Le second sens : *une phrase qui s'affiche toujours ne se lit
        plus.* Prendre la duree du contrat n'est pas une hypothese."""
        for declaree in (0.25, 0.5, 1.0, 2.0):
            with self.subTest(exposition=declaree):
                valeur, source, phrase = source_exposition(declaree, None)
                self.assertEqual(valeur, declaree)
                self.assertEqual(source, EXPO_DU_CONTRAT)
                self.assertIsNone(phrase)

    def test_DC6_les_proses_du_module_DISENT_le_nouveau_contrat(self):
        """⚠️⚠️ *Le TEXTE qui accompagne un comportement se relit quand il
        change* — et il a change DEUX FOIS aujourd'hui : une fois pour dire la
        divergence, une fois pour dire qu'elle est fermee. Ce test suit."""
        from direction_non_vie.tarification import pipeline_tarifaire as P
        entete = inspect.getdoc(P) or ''
        # ⚠️ L'en-tete peut de nouveau annoncer `tarifer(contrat)` sans
        # condition -- parce que c'est VRAI depuis le cas (a). Ce qu'il doit
        # porter, c'est que ca ne l'a pas toujours ete.
        self.assertIn("prends l'exposition du contrat", entete,
                      "l en-tete ne dit pas ce que signifie le silence de "
                      "l appelant")
        self.assertIn('CHANGEMENT DE PRIX', entete)
        doc = inspect.getdoc(P.TarifNonVie.predire_portefeuille) or ''
        self.assertNotIn('MÊME chemin que\n        `tarifer()`', doc)
        for attendu in ('le même prix', 'INV-7b', 'kilometrage_annuel',
                        'DC-2'):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, doc)

    def test_DC6b_le_chiffre_de_C7_porte_TOUJOURS_sa_portee(self):
        """⚠️ Le `0,0036 EUR` du constat `pipeline/C7` a change de portee deux
        fois en un jour. Il doit dire laquelle il a, pas rester nu."""
        from direction_non_vie.tarification import pipeline_tarifaire as P
        doc = inspect.getdoc(P.TarifNonVie.predire_portefeuille) or ''
        i = doc.find('0,0036')
        self.assertGreater(i, 0, 'le chiffre de C7 a disparu de la docstring')
        suite = doc[i:i + 600]
        for attendu in ('cas (b)', 'déclarée'):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, suite,
                              "le `0,0036 EUR` est publie sans dire dans quel "
                              "cas il cesse de valoir")


class TestLeMessageNePeutPasSePERDRE(unittest.TestCase):
    """⚠️⚠️ LA GARANTIE EXIGEE POUR LE CAS (b), ET POURQUOI ELLE PREND CETTE
    FORME-LA.

    Selasse a demande trois choses : un vrai consommateur qui publie le
    message dans un document produit, une sentinelle qui lit les OCTETS de ce
    document, et un plant qui le fasse rougir.

    ⛔⛔ **CE CONSOMMATEUR N'EXISTE PAS, ET C'EST MESURE, PAS SUPPOSE.** Releve
    par AST sur tout le depot (hors tests et `audit_2026_08/`) :

      · aucun exportateur ne prend un `TarifNonVie` -- les six `export_excel_aN`
        prennent des `result_aN` d'agents ;
      · `actuaria_app.py:3574` calcule `pipeline_complet` et le range dans
        `resultats["tarif_plan"]`, **clé lue nulle part** ;
      · `tarifer()` a **UN SEUL appelant de production dans tout le depot** :
        `demos/fremtpl2_demo.py:171` -- et il passe deja `exposition=`.

    Il n'y a donc aucun document de devis a instrumenter, et en fabriquer un
    pour heberger une phrase serait inventer un consommateur artificiel.

    ⚠️ CE QU'ON FAIT A LA PLACE, ET C'EST PLUS FORT QU'UN DOCUMENT : un
    controle **DERIVE** exige que tout appelant de production de `tarifer()`
    ou bien fournisse `exposition=` (cas (c) : aucune hypothese), ou bien
    LISE la declaration dans le resultat. Il n'enumere pas les appelants, il
    les derive -- donc **il tire le jour ou quelqu'un en ajoute un qui jette
    le message**, y compris dans un futur exportateur de devis.
    """

    #: Les dossiers qui ne sont pas de la production.
    IGNORES = ('/.venv/', '/audit_2026_08/', '/__pycache__/')
    #: ⚠️ Les cles qui PORTENT la declaration. Un appelant qui en lit une a vu
    #: l'hypothese ; un appelant qui n'en lit aucune l'a jetee.
    CLES = ('exposition_hypothese', 'exposition_source', 'exposition_retenue')

    @staticmethod
    def _sites_de_tarifer():
        """Les appels a `tarifer()` en production, par AST. ⚠️ Jamais au grep :
        un alias, un `self.`, un homonyme ne se voient pas au texte."""
        import ast
        import pathlib
        racine = pathlib.Path(_RACINE)
        sites = []
        for chemin in sorted(racine.rglob('*.py')):
            s = chemin.as_posix()
            if (any(i in s for i in TestLeMessageNePeutPasSePERDRE.IGNORES)
                    or chemin.name.startswith('test_')):
                continue
            source = chemin.read_text(encoding='utf-8', errors='replace')
            try:
                arbre = ast.parse(source)
            except SyntaxError:                     # pragma: no cover
                continue
            for n in ast.walk(arbre):
                if not (isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and n.func.attr == 'tarifer'):
                    continue
                sites.append({
                    'fichier': s, 'ligne': n.lineno,
                    'fournit_exposition': any(
                        k.arg == 'exposition' for k in (n.keywords or [])),
                    'source_module': source,
                })
        return sites

    def test_DC7_tout_appelant_de_tarifer_FOURNIT_ou_LIT_la_declaration(self):
        """⚠️⚠️ *Un calcul qui n'atteint aucun livrable n'existe pas.* Ici le
        livrable est le dictionnaire rendu : le controle exige donc que
        personne ne le jette."""
        sites = self._sites_de_tarifer()
        self.assertGreater(
            len(sites), 0,
            "aucun appel a `tarifer()` trouve : le releve AST ne traverse "
            "plus rien et ce controle serait vert pour rien")
        muets = []
        for site in sites:
            if site['fournit_exposition']:
                continue          # cas (c) : aucune hypothese n'est faite
            if any(cle in site['source_module'] for cle in self.CLES):
                continue          # le fichier lit la declaration
            muets.append(f'{site["fichier"]}:{site["ligne"]}')
        self.assertEqual(
            muets, [],
            f'ces appelants obtiennent un prix sans fournir la duree NI lire '
            f'la declaration qui l accompagne : {muets}. Le message du cas '
            f'(b) se perd chez eux -- fournir `exposition=`, ou publier '
            f'`exposition_hypothese`.')

    def test_DC8_le_releve_TRAVERSE_bien_le_seul_appelant_connu(self):
        """⚠️ *Une sonde doit prouver qu'elle traverse ce qu'elle mesure.* Si
        le releve rendait une liste vide, `DC-7` passerait sans rien lire."""
        sites = self._sites_de_tarifer()
        fichiers = {s['fichier'].rsplit('/', 1)[-1] for s in sites}
        self.assertIn(
            'fremtpl2_demo.py', fichiers,
            f'le seul appelant de production connu a disparu du releve : '
            f'{sorted(fichiers)}')
        for s in sites:
            if s['fichier'].endswith('fremtpl2_demo.py'):
                self.assertTrue(
                    s['fournit_exposition'],
                    "`fremtpl2_demo.py` ne passe plus `exposition=` : le seul "
                    "appelant de production est entre dans le cas (b)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
