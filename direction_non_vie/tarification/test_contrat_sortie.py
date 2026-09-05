# -*- coding: utf-8 -*-
"""UN AGENT REND TOUJOURS LES MEMES CLES — LA RACINE DU `.get(cle, litteral)`.

Un lecteur ne pose un littéral que parce qu'AUCUNE clé ne lui est garantie.
Le lot precedent a retire 101 de ces litteraux ; celui-ci ferme la raison
qui les faisait ecrire.

⚠️⚠️ LE CONTRAT NE SE DECLARE PAS, IL SE DERIVE : on compare l'agent A
LUI-MEME, sur deux executions reelles -- un chemin nominal et un chemin
d'echec. Aucune liste tenue a la main ne peut donc diverger.

CE QUI A ETE MESURE LE 05/09/2026 :

  1. `A1.run` AVAIT QUATRE SORTIES : une complete a SEIZE cles, et TROIS
     chemins d'echec a HUIT. Manquaient `qualite`, `rapport`, `hash_md5`,
     `client_id`, `audit_trail` et les trois cles de livrable -- que
     `tarif_excel` et `rapport_equipe_tarif` LISENT. Des qu'A1 echouait,
     ces lecteurs recevaient leur littéral, sans le savoir.

  2. QUATRE CLES SONT LUES SUR `result_a6` QU'A6 NE PUBLIE JAMAIS. Trois
     sont dans A8 (hors perimetre, voir CS-5). La quatrieme etait dans la
     TARIFICATION : `rapport_equipe_tarif` faisait
     `(r6.get('plan') or {}).get('lob', '')` sur les 51 cles d'A6, dont
     aucune ne s'appelle `plan`. Le nom valait donc toujours `''`, et les
     TROIS surfaces signees publiaient
     << ACTION REQUISE -- plan '?' : N facteur(s) DECLARE(S) ... RETIRE(S) >>.
     Sur un portefeuille de vingt plans, l'actuaire apprend qu'un plan a un
     probleme sans savoir lequel.

  3. ET LES SIX TESTS DE `test_colonnes_plan_ecartees` PASSAIENT 'auto' EN
     DUR a la fonction. Ils attestaient le libelle sans jamais passer par
     le site de production -- l'asymetrie entre les tests et les trois
     appelants reels etait le seul revelateur.

  4. `core/base_agent.RETOUR_VIDE` declare quinze cles, dont `triangle`
     (une notion de PROVISIONNEMENT), et compte ZERO heritier dans tout le
     depot. Ce n'est pas une source a reutiliser : c'est un contrat que
     personne n'a jamais signe. Le contrat de la tarification vit donc dans
     la tarification -- ce qui est aussi ce qui se vend avec elle.

Ce que cette sentinelle exige :
  CS-1  chaque agent rend le MEME jeu de cles en echec et en succes ;
  CS-2  le gabarit REFUSE une cle qu'il ne connait pas ;
  CS-3  aucun lecteur de la tarification ne lit une cle qu'aucun agent ne
        publie ;
  CS-4  le nom du plan atteint les TROIS surfaces signees ;
  CS-5  les lectures hors perimetre sont NOMMEES et leur nombre est fige.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""
import ast
import glob
import logging
import os
import pathlib
import sys
import unittest
import warnings

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

import numpy as np

from core.conformite_reglementaire import synthese_colonnes_plan_ecartees
from direction_non_vie.tarification import test_pipeline_agents as T
from direction_non_vie.tarification.a1_ingestion.agent import (
    GABARIT_SORTIE,
    AgentA1Ingestion,
)
from direction_non_vie.tarification.contrat_sortie import sortie_completee

# =============================================================================
#  CS-1, CS-2 — LE CONTRAT, VERIFIE PAR EXECUTION
# =============================================================================

class TestMemesClesPartout(unittest.TestCase):
    """⚠️ PAR EXECUTION, PAS PAR AST. Un gabarit peut etre etale
    (`{**GABARIT, ...}`), passe par une fonction, ou construit en boucle :
    seule l'execution voit ce qui SORT vraiment."""

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)
        np.random.seed(7)
        cls.df = T._portefeuille_auto(600)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def _a1(self):
        return AgentA1Ingestion(audit_path='/tmp', verbose=False)

    def test_CS1_A1_rend_les_memes_cles_sur_ses_QUATRE_chemins(self):
        succes = self._a1().run(branche='non_vie', sous_branche='auto',
                                dataframe=self.df)
        self.assertTrue(succes['success'], succes.get('erreur'))
        echecs = {
            'branche hors perimetre': self._a1().run(
                branche='vie', sous_branche='auto', dataframe=self.df),
            'sous_branche absente': self._a1().run(
                branche='non_vie', sous_branche='', dataframe=self.df),
            'exception interne': self._a1().run(
                branche='non_vie', sous_branche='auto',
                dataframe='ceci n est pas un dataframe'),
        }
        for nom, sortie in echecs.items():
            with self.subTest(chemin=nom):
                self.assertFalse(sortie['success'],
                                 f'{nom} : ce chemin devait echouer')
                self.assertEqual(
                    sorted(sortie), sorted(succes),
                    f"{nom} : A1 ne rend pas les memes cles qu'en succes. "
                    f"Manquantes : {sorted(set(succes) - set(sortie))} ; "
                    f"en trop : {sorted(set(sortie) - set(succes))}")

    def test_CS1b_les_cles_LUES_par_les_livrables_sont_toutes_la(self):
        """⚠️ L'assiette se DECLARE : ce sont les cles qu'un livrable lit
        reellement sur un resultat A1, relevees par AST ci-dessous (CS-3)."""
        echec = self._a1().run(branche='vie', sous_branche='auto',
                               dataframe=self.df)
        for cle in ('qualite', 'rapport', 'hash_md5', 'audit_trail',
                    'excel_bytes', 'client_id'):
            self.assertIn(cle, echec,
                          f"{cle} absente d'un A1 en echec : ses lecteurs "
                          'recevront leur littéral')

    def test_CS2_le_gabarit_REFUSE_une_cle_inconnue(self):
        """Sans ce refus, un chemin d'echec pourrait publier une cle de plus
        que le chemin normal, et CS-1 rougirait sans qu'on sache pourquoi."""
        with self.assertRaises(KeyError) as capture:
            sortie_completee(GABARIT_SORTIE, cle_inventee=1)
        self.assertIn('cle_inventee', str(capture.exception))

    def test_CS2b_le_gabarit_ne_se_partage_pas_entre_appels(self):
        """Un dict de module modifie par un appel contaminerait le suivant."""
        premiere = sortie_completee(GABARIT_SORTIE, branche='auto')
        premiere['qualite']['pollution'] = True
        seconde = sortie_completee(GABARIT_SORTIE, branche='mrh')
        self.assertEqual(GABARIT_SORTIE['branche'], '',
                         'le gabarit de module a ete modifie')
        self.assertNotIn('pollution', seconde['qualite'],
                         'deux sorties partagent le meme dict `qualite`')


# =============================================================================
#  CS-3, CS-5 — LA FRONTIERE : QUI LIT QUOI, ET QUI LE PUBLIE ?
# =============================================================================

_AGENTS = {
    'A1': 'direction_non_vie/tarification/a1_ingestion/agent.py',
    'A2': 'direction_non_vie/tarification/a2_preprocessing/agent.py',
    'A3': 'direction_non_vie/tarification/a3_glm/agent.py',
    'A4': 'direction_non_vie/tarification/a4_ml/agent.py',
    'A5': 'direction_non_vie/tarification/a5_deep_learning/agent.py',
    'A6': 'direction_non_vie/tarification/a6_comparaison/agent.py',
}

#: nom de variable -> agent dont c'est le resultat.
_BASES = {'result_a1': 'A1', 'result_a2': 'A2', 'result_a3': 'A3',
          'result_a4': 'A4', 'result_a5': 'A5', 'result_a6': 'A6',
          'r1': 'A1', 'r2': 'A2', 'r3': 'A3', 'r4': 'A4', 'r5': 'A5',
          'r6': 'A6', '_tmp_a4': 'A4', '_tmp_a6': 'A6'}

#: ⚠️⚠️ LES LECTURES HORS PERIMETRE, NOMMEES ET FIGEES. `A8` lit sur
#: `result_a6` trois cles qu'A6 ne publie pas. Elles ne sont PAS corrigees
#: ici : la reglementation (A8-A14) est hors du perimetre arbitre, et rien ne
#: s'y ouvre sans accord. Elles sont inscrites pour que le controle ne les
#: CACHE pas -- et parce qu'une quatrieme ferait rougir cette liste.
#:
#:   `a8:329  result_a6.get('loss_ratio_attendu', 0.72)` -- A6 ne publie
#:   JAMAIS cette cle : le 0,72 se pose donc a CHAQUE run, il est journalise
#:   sous << A6 branche >>, et `a8:1084` fait `if lr_attendu > 0.85` pour
#:   declencher l'action << Resserrer les criteres de souscription >>. Cette
#:   recommandation est donc STRUCTURELLEMENT inatteignable.
#:   `a8:328  result_a6.get('gini', 0.25)` et
#:   `a8:330  result_a6.get('modele_retenu', 'N/A')` sont, eux, proteges par
#:   une premiere lecture sur `modele_production`.
LECTURES_HORS_PERIMETRE = {
    ('A6', 'gini'), ('A6', 'loss_ratio_attendu'), ('A6', 'modele_retenu'),
}


def _cles_publiees(chemin):
    arbre = ast.parse(pathlib.Path(chemin).read_text(encoding='utf-8'))
    cles = set()
    for n in ast.walk(arbre):
        if not (isinstance(n, ast.FunctionDef) and n.name == 'run'):
            continue
        for sub in ast.walk(n):
            if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                cles |= {k.value for k in sub.value.keys
                         if isinstance(k, ast.Constant)
                         and isinstance(k.value, str)}
            # `return sortie_completee(GABARIT, ...)` : le gabarit porte les cles
            elif (isinstance(sub, ast.Return) and isinstance(sub.value, ast.Call)
                  and getattr(sub.value.func, 'id', None) == 'sortie_completee'):
                cles |= set(GABARIT_SORTIE)
    return cles


def _lectures(zones):
    lues = []
    for motif in zones:
        for f in glob.glob(os.path.join(_RACINE, motif), recursive=True):
            chemin = f.replace('\\', '/')
            nom = pathlib.Path(chemin).name
            if ('__pycache__' in chemin or 'audit_2026_08' in chemin
                    or nom.startswith('test_')):
                continue
            try:
                arbre = ast.parse(pathlib.Path(chemin).read_text(encoding='utf-8'))
            except (SyntaxError, UnicodeDecodeError):               # pragma: no cover
                continue
            for n in ast.walk(arbre):
                base = cle = None
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                        and n.func.attr == 'get' and n.args
                        and isinstance(n.args[0], ast.Constant)
                        and isinstance(n.args[0].value, str)
                        and isinstance(n.func.value, ast.Name)):
                    base, cle = n.func.value.id, n.args[0].value
                elif (isinstance(n, ast.Subscript)
                      and isinstance(n.value, ast.Name)
                      and isinstance(n.slice, ast.Constant)
                      and isinstance(n.slice.value, str)):
                    base, cle = n.value.id, n.slice.value
                if base in _BASES:
                    lues.append((_BASES[base], cle, chemin, n.lineno))
    return lues


class TestFrontiere(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.publiees = {code: _cles_publiees(os.path.join(_RACINE, chemin))
                        for code, chemin in _AGENTS.items()}

    def test_CS3_aucun_lecteur_de_la_tarification_ne_lit_une_cle_fantome(self):
        """⚠️⚠️ C'est ce controle qui a trouve `r6['plan']`. Il DERIVE les
        cles publiees des `return` de chaque agent : rien n'est enumere."""
        for code in _AGENTS:
            self.assertTrue(self.publiees[code],
                            f'{code} : aucune cle publiee relevee, le '
                            'controle ne mesure rien')
        fantomes = []
        for code, cle, chemin, ligne in _lectures(
                ('direction_non_vie/tarification/**/*.py',)):
            if cle not in self.publiees[code]:
                fantomes.append(f'{pathlib.Path(chemin).name}:{ligne} lit '
                                f'{code}[{cle!r}] -- jamais publiee')
        self.assertEqual(fantomes, [], 'cle(s) lue(s) que personne ne '
                                       'publie :\n  ' + '\n  '.join(fantomes))

    def test_CS5_les_lectures_hors_perimetre_sont_nommees_et_figees(self):
        """⚠️⚠️ ELLES NE SONT PAS CORRIGEES, ELLES SONT DECLAREES. La
        reglementation est hors du perimetre arbitre. Ce test EXISTE pour que
        le controle ne les cache pas : une quatrieme le fait rougir, et leur
        correction aussi -- ce qui obligera a relire cette liste."""
        dehors = set()
        for code, cle, _, _ in _lectures(
                ('direction_non_vie/reglementation/**/*.py',
                 'direction_non_vie/provisionnement/**/*.py')):
            if cle not in self.publiees.get(code, set()):
                dehors.add((code, cle))
        self.assertEqual(
            dehors, LECTURES_HORS_PERIMETRE,
            'la liste des lectures fantomes hors perimetre a change.\n'
            f'  apparues : {sorted(dehors - LECTURES_HORS_PERIMETRE)}\n'
            f'  disparues : {sorted(LECTURES_HORS_PERIMETRE - dehors)}')


# =============================================================================
#  CS-4 — LE NOM DU PLAN ATTEINT LES TROIS SURFACES
# =============================================================================

class TestNomDuPlanPublie(unittest.TestCase):

    #: Les trois APPELANTS de ce libelle.
    #: ⚠️⚠️ CORRECTION DU 05/09/2026, MESUREE DANS LES OCTETS : ce ne sont PAS
    #: trois surfaces signees. Le libelle << ACTION REQUISE -- plan '...' >>
    #: atteint l'Excel A6 et le rapport d'equipe (HTML et Word), qui nomment
    #: bien le plan. Le troisieme appelant, dans `rapport_modeles_tarif`,
    #: vit dans `_construire_contexte_tarif` : il alimente LE PROMPT LLM, pas
    #: le document -- et le Word/HTML d'A6 ne publient ce libelle sur AUCUN
    #: chemin. Le correctif reste juste aux trois endroits (le prompt nourrit
    #: une narration publiee) ; c'est le DECOMPTE qui etait faux.
    SURFACES = (
        'direction_non_vie/tarification/services/tarif_excel.py',
        'direction_non_vie/tarification/services/rapport_modeles_tarif.py',
        'direction_non_vie/tarification/services/rapport_equipe_tarif.py',
    )

    def test_CS4_les_trois_appelants_passent_un_nom_de_plan(self):
        """⚠️⚠️ AUCUN NE LE PASSAIT. Deux appelaient sans second argument, le
        troisieme passait une expression toujours vide. Les six tests de
        `test_colonnes_plan_ecartees`, eux, passent 'auto' EN DUR : ils
        attestaient le libelle sans jamais passer par le site de production.
        *Un controle qui n'emprunte pas le chemin reel n'en surveille rien.*

        ⚠️ Ce controle porte sur les APPELANTS. La preuve que le nom atteint
        REELLEMENT les octets publies est ailleurs : `test_faits_publies`
        cherche << plan 'auto' >> dans le classeur A6 et le rapport d'equipe.
        """
        muets = []
        for chemin in self.SURFACES:
            plein = os.path.join(_RACINE, chemin)
            arbre = ast.parse(pathlib.Path(plein).read_text(encoding='utf-8'))
            vus = 0
            for n in ast.walk(arbre):
                if not (isinstance(n, ast.Call)
                        and getattr(n.func, 'id', getattr(n.func, 'attr', None))
                        == 'synthese_colonnes_plan_ecartees'):
                    continue
                vus += 1
                if len(n.args) < 2:
                    muets.append(f'{pathlib.Path(chemin).name}:{n.lineno} '
                                 "n'a pas d'argument de nom de plan")
                elif 'branche' not in ast.unparse(n.args[1]):
                    muets.append(f'{pathlib.Path(chemin).name}:{n.lineno} '
                                 f'passe {ast.unparse(n.args[1])!r}, qui ne '
                                 "derive pas de l'identite publiee par l'agent")
            self.assertGreater(vus, 0, f'{chemin} : appel introuvable, cette '
                                       'surface a-t-elle change ?')
        self.assertEqual(muets, [], '\n  '.join(muets))

    def test_CS4b_le_libelle_publie_NOMME_le_plan(self):
        """La contre-epreuve, sur la vraie fonction : un nom vide se voit."""
        ecartees = {'bonus_malus': 'retiree par un filtre amont'}
        avec = synthese_colonnes_plan_ecartees(ecartees, 'auto')
        sans = synthese_colonnes_plan_ecartees(ecartees, '')
        self.assertIn("plan 'auto'", avec, avec)
        self.assertIn("plan '?'", sans,
                      "le libelle ne signale plus l'absence de nom : ce test "
                      'ne surveille plus rien')


if __name__ == '__main__':
    unittest.main(verbosity=2)
