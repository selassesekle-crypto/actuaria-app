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

# ⚠️ `GABARIT_SORTIE` EST ICI CELUI D'A1, ET IL NE SERT QU'A CS-2 (le
# gabarit refuse-t-il une cle inconnue ?). ⛔ NE PAS s'en servir pour
# DERIVER les cles d'un autre agent : c'est exactement le defaut que
# `_gabarit_du_fichier` a ferme le 11/09/2026 -- 15 lectures reelles
# declarees fantomes parce qu'A4 avait adopte le contrat.
from direction_non_vie.tarification.a1_ingestion.agent import (
    GABARIT_SORTIE,
    AgentA1Ingestion,
)
from direction_non_vie.tarification.contrat_sortie import (
    FORMES_VIDES,
    sortie_completee,
)

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


def _gabarit_du_fichier(arbre):
    """Les cles du `GABARIT_SORTIE` declare DANS CE MODULE-LA.

    ⚠️⚠️ CE RELEVE LISAIT LE GABARIT D'A1 POUR LES SIX AGENTS. La ligne
    fautive etait `cles |= set(GABARIT_SORTIE)` : `GABARIT_SORTIE` est ici
    l'objet IMPORTE EN TETE DE CE FICHIER, `a1_ingestion.GABARIT_SORTIE`,
    dix-sept cles. Tant qu'A1 etait le seul agent migre vers
    `sortie_completee`, la confusion ne se voyait pas.

    Mesure du 11/09/2026, sur une copie isolee ou A4 passe par
    `sortie_completee` avec SON propre gabarit de 37 cles : **CS-3 rougit sur
    15 lectures reelles** -- `tarif_excel:361 lit A4['validation_ml']`,
    `a6:1488 lit A4['col_cible']`, `rapport_equipe_tarif:567 lit
    A4['classement']`... toutes publiees par A4, aucune presente dans le
    gabarit d'A1.

      *La sentinelle ecrite pour garantir le contrat PUNISSAIT l'agent qui
      adopte le contrat.* C'est le meme defaut qu'elle denonce chez les
      autres : une reference lue a cote de la donnee qu'elle decrit.

    ⚠️ ON DERIVE, ON N'IMPORTE PAS : le gabarit se lit dans l'arbre de
    l'agent examine. Aucune table, aucun import a tenir a jour, et un
    septieme agent entre dans la mesure sans que cette fonction change.
    """
    cles = set()
    for n in arbre.body:
        cible = None
        if isinstance(n, ast.AnnAssign):
            cible = getattr(n.target, 'id', None)
        elif isinstance(n, ast.Assign) and len(n.targets) == 1:
            cible = getattr(n.targets[0], 'id', None)
        if cible == 'GABARIT_SORTIE' and isinstance(n.value, ast.Dict):
            cles |= {k.value for k in n.value.keys
                     if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return cles


def _cles_publiees(chemin):
    arbre = ast.parse(pathlib.Path(chemin).read_text(encoding='utf-8'))
    gabarit = _gabarit_du_fichier(arbre)
    cles = set()
    for n in ast.walk(arbre):
        if not (isinstance(n, ast.FunctionDef) and n.name == 'run'):
            continue
        for sub in ast.walk(n):
            if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                cles |= {k.value for k in sub.value.keys
                         if isinstance(k, ast.Constant)
                         and isinstance(k.value, str)}
            # `return sortie_completee(GABARIT, ...)` : le gabarit porte les
            # cles -- CELUI DE CET AGENT, lu dans son propre module.
            elif (isinstance(sub, ast.Return) and isinstance(sub.value, ast.Call)
                  and getattr(sub.value.func, 'id', None) == 'sortie_completee'):
                if not gabarit:
                    raise AssertionError(
                        f'{pathlib.Path(chemin).name} : `run` rend un '
                        '`sortie_completee(...)` mais ce module ne declare '
                        'aucun `GABARIT_SORTIE` -- le controle ne peut pas '
                        'deriver ses cles publiees, et un gabarit emprunte '
                        'a un autre agent le rendrait FAUX.')
                cles |= gabarit
                # ⚠️ Et les cles passees en clair au meme appel : un agent
                # peut poser une valeur hors gabarit -- `sortie_completee`
                # leverait, mais le relevé, lui, doit rester fidele a ce que
                # le code ECRIT.
                cles |= {kw.arg for kw in sub.value.keywords if kw.arg}
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


# =============================================================================
#  CS-1c — LE CONTRAT EST VERIFIE SUR LES SIX AGENTS, PLUS SUR UN SEUL
# =============================================================================

class TestContratSurLesSixAgents(unittest.TestCase):
    """⚠️⚠️ CS-1 CI-DESSUS N'EXERCE QUE A1, ET LE MODULE PROMET LES SIX.

    Son en-tete dit « un agent rend TOUJOURS LES MEMES CLES » et
    `contrat_sortie` le repete ; `TestMemesClesPartout` n'instancie qu'A1.
    Mesure du 11/09/2026, par EXECUTION de chaque `_erreur`, comparee aux
    cles d'un run reel :

        agent   cles a l'echec   cles au succes   PERDUES
         A1        17               17               0
         A2         9               16               7
         A3        11               38              27
         A4        13               37              24
         A5        12               28              16
         A6        12               53              41

    Et les quatre cles du contrat -- `excel_bytes`, `word_bytes`,
    `pdf_bytes`, `audit_trail` -- manquaient au chemin d'echec de CINQ
    agents sur six.

      *Une sentinelle braquee sur un sixieme de son sujet certifie ce
      qu'elle n'a pas regarde.*

    ⚠️ LA LISTE DES AGENTS SE DERIVE DE `_AGENTS`, deja tenue par CS-3 :
    une seconde liste divergerait de la premiere.
    """

    #: nom de module -> nom de la classe d'agent. ⚠️ Il n'y a PAS de table :
    #: la classe est trouvee dans le module par son nom, qui commence tous
    #: par `Agent`. Un septieme agent entre sans toucher a ce test.
    @staticmethod
    def _classe_agent(module):
        import inspect
        for nom, objet in vars(module).items():
            if (inspect.isclass(objet) and nom.startswith('Agent')
                    and objet.__module__ == module.__name__):
                return objet
        return None

    @staticmethod
    def _module(code):
        import importlib
        chemin = _AGENTS[code].replace('/', '.').removesuffix('.py')
        return importlib.import_module(chemin)

    def test_CS1c_chaque_agent_declare_un_gabarit_de_sortie(self):
        """Sans gabarit, aucun chemin ne peut garantir les memes cles."""
        sans = [code for code in sorted(_AGENTS)
                if getattr(self._module(code), 'GABARIT_SORTIE', None) is None]
        self.assertEqual(
            sans, [],
            f"{sans} ne declare(nt) aucun GABARIT_SORTIE : leur chemin "
            f"d'echec ne peut pas rendre les memes cles que leur chemin "
            f"complet, et rien ne le detecte.")

    def test_CS1c_le_chemin_d_echec_rend_EXACTEMENT_le_gabarit(self):
        """⚠️ PAR EXECUTION : on appelle `_erreur` et on lit ce qui SORT."""
        for code in sorted(_AGENTS):
            with self.subTest(agent=code):
                module = self._module(code)
                gabarit = getattr(module, 'GABARIT_SORTIE', None)
                self.assertIsNotNone(gabarit, f'{code} : aucun gabarit')
                classe = self._classe_agent(module)
                self.assertIsNotNone(classe, f'{code} : classe introuvable')
                agent = classe.__new__(classe)
                _erreur = getattr(agent, '_erreur', None)
                if _erreur is None:
                    # A1 n'a pas de `_erreur` : ses chemins d'echec appellent
                    # `sortie_completee` directement, et CS-1 les execute deja.
                    continue
                sortie = _erreur('sonde de contrat', 'AUDIT-CS1c')
                self.assertEqual(
                    sorted(sortie), sorted(gabarit),
                    f"{code} : le chemin d'echec ne rend pas le gabarit. "
                    f"Manquantes : {sorted(set(gabarit) - set(sortie))} ; "
                    f"en trop : {sorted(set(sortie) - set(gabarit))}")

    def test_CS1c_les_quatre_cles_de_livrable_sont_au_gabarit(self):
        """⚠️⚠️ CE SONT ELLES QUE `gel_livrables` ENUMERE.

        `livrables_d_un_resultat` parcourt les cles finissant par `_bytes`.
        Un agent qui n'en publie aucune sur son chemin d'echec fait SORTIR
        ses surfaces de l'assiette de l'instrument de non-regression, qui
        rapporte alors << 0 ecart >> sur ce qu'il ne regarde plus.
        """
        for code in sorted(_AGENTS):
            with self.subTest(agent=code):
                gabarit = getattr(self._module(code), 'GABARIT_SORTIE', {})
                manquantes = [cle for cle in FORMES_VIDES
                              if cle in ('excel_bytes', 'word_bytes',
                                         'pdf_bytes', 'audit_trail')
                              and cle not in gabarit]
                self.assertEqual(
                    manquantes, [],
                    f'{code} : {manquantes} absente(s) du gabarit — les '
                    f'surfaces de cet agent sortent de l assiette du gel des '
                    f'que son run echoue.')

    def test_CS1c_les_DEUX_chemins_passent_par_le_gabarit(self):
        """⚠️ CE CONTROLE-CI EST STRUCTUREL, ET JE LE DIS.

        Les trois precedents s'executent. Celui-ci ne le peut pas : faire
        REUSSIR les six agents demanderait un portefeuille, un plan et
        plusieurs minutes de calibration par agent. Il verifie donc que le
        `return` du chemin COMPLET passe lui aussi par
        `sortie_completee(GABARIT_SORTIE, ...)` -- ce qui rend l'egalite des
        cles structurelle plutot que constatee.

        *Un controle structurel qui se declare tel vaut mieux qu'un controle
        par execution qui n'a pas lieu.*
        """
        for code in sorted(_AGENTS):
            with self.subTest(agent=code):
                arbre = ast.parse(pathlib.Path(
                    os.path.join(_RACINE, _AGENTS[code])).read_text(
                        encoding='utf-8'))
                complets, bruts = 0, 0
                for n in ast.walk(arbre):
                    if not (isinstance(n, ast.FunctionDef) and n.name == 'run'):
                        continue
                    for sub in ast.walk(n):
                        if not isinstance(sub, ast.Return):
                            continue
                        if isinstance(sub.value, ast.Dict):
                            bruts += 1
                        elif (isinstance(sub.value, ast.Call)
                              and getattr(sub.value.func, 'id', None)
                              == 'sortie_completee'):
                            complets += 1
                self.assertEqual(
                    bruts, 0,
                    f"{code} : {bruts} `return {{...}}` brut(s) dans `run` — "
                    f"ces chemins ne passent pas par le gabarit et peuvent "
                    f"donc publier un jeu de cles different de `_erreur`.")
                self.assertGreater(
                    complets, 0,
                    f'{code} : aucun `return sortie_completee(...)` dans '
                    f'`run` — le contrat n est pas applique.')


# =============================================================================
#  CS-1d — LE CHEMIN DE SUCCES TIENT-IL DANS SON PROPRE GABARIT ?
# =============================================================================

class TestSuccesTientDansLeGabarit(unittest.TestCase):
    """⚠️⚠️ CE QUE LES QUATRE CS-1c NE VOIENT PAS, ET CE QUE ÇA A COUTÉ.

    `CS-1c (2)` exécute `_erreur`. `CS-1c (4)` est STRUCTUREL : il compte
    les `return` bruts, il n'exerce pas le chemin de succès — faire
    réussir six agents demanderait plusieurs minutes de calibration
    chacun. **Entre les deux, le chemin nominal n'est mesuré par
    personne**, et c'est celui qui publie.

    MESURE DU 15/09/2026, PAR LE GEL, PAS PAR CETTE SUITE :

      A6 construit son résultat avec `**_relais_prix` — un dict bâti
      l.1257, né le 14/09 (`18be214`), TROIS JOURS après la mesure sur
      laquelle le gabarit de 53 clés a été écrit. Ses cinq clés
      (`tarif`, `portefeuille_tarife`, `comparaison_prix`,
      `conditions_mesure`, `decision_actuaire`) étaient donc HORS
      gabarit. `sortie_completee` a levé — exactement son rôle — et le
      `except Exception` de `run` a converti l'alarme en `_erreur` :

          a6 Excel, a6 HTML, a6 Word  ->  `<livrable absent>`
          2 488 écarts au gel, DOUZE tests de cette suite VERTS

    *Un garde-fou qui lève dans un `except` large ne protège plus : il
    se tait.* Ce contrôle-ci refait STATIQUEMENT ce que
    `sortie_completee` fait à l'exécution — `set(valeurs) - set(gabarit)`
    — et il RÉSOUT les `**` étalés, que l'AST ne voit pas autrement.

    ⚠️ SON ASSIETTE SE DÉCLARE : un `**expression` qu'il ne sait PAS
    résoudre le fait ÉCHOUER, jamais passer. Une assiette muette sur ce
    qu'elle ne voit pas est ce qui a produit ce défaut.
    """

    @staticmethod
    def _dict_nomme(fonction, nom):
        """Le dernier dict littéral affecté à `nom` dans cette fonction."""
        trouve = None
        for n in ast.walk(fonction):
            if (isinstance(n, ast.Assign) and len(n.targets) == 1
                    and getattr(n.targets[0], 'id', None) == nom
                    and isinstance(n.value, ast.Dict)):
                trouve = n.value
        return trouve

    def _etale(self, noeud, porteuse, code, ligne):
        """Le dict que `**noeud` étale, résolu — ou l'échec, jamais le vide.

        ⚠️ A6 en porte DEUX NIVEAUX : `**{... , **_relais_prix}`. Une
        première version de ce contrôle s'arrêtait au premier, accusait
        « `**` imbriqué » et refusait — donc rouge pour la mauvaise
        raison. La résolution est RÉCURSIVE.
        """
        source = noeud
        if isinstance(source, ast.Name):
            source = self._dict_nomme(porteuse, source.id)
        self.assertIsInstance(
            source, ast.Dict,
            f'{code}:{ligne} — `**{ast.unparse(noeud)[:40]}` n est pas un '
            f'dict litteral resoluble dans `{porteuse.name}` : ce controle '
            f'ne sait PAS voir ses cles, et il refuse de passer sur une '
            f'assiette qu il ne voit pas.')
        return source

    def _cles_dun_dict(self, noeud, porteuse, code, ligne):
        cles = set()
        for cle, valeur in zip(noeud.keys, noeud.values):
            if cle is None:                      # `**autre` étalé ici
                cles |= self._cles_dun_dict(
                    self._etale(valeur, porteuse, code, ligne),
                    porteuse, code, ligne)
                continue
            self.assertTrue(
                isinstance(cle, ast.Constant) and isinstance(cle.value, str),
                f'{code}:{ligne} — cle non litterale, non resolue, refusee.')
            cles.add(cle.value)
        return cles

    def _cles_dun_appel(self, appel, porteuse, code):
        """Les clés que cet appel passera à `sortie_completee`, toutes."""
        cles = set()
        for kw in appel.keywords:
            if kw.arg:
                cles.add(kw.arg)
                continue
            cles |= self._cles_dun_dict(
                self._etale(kw.value, porteuse, code, appel.lineno),
                porteuse, code, appel.lineno)
        return cles

    def test_CS1d_aucun_appel_ne_passe_une_cle_hors_gabarit(self):
        """`sortie_completee` LEVE sur ces clés-là. Ici on les nomme AVANT."""
        for code in sorted(_AGENTS):
            with self.subTest(agent=code):
                chemin = os.path.join(_RACINE, _AGENTS[code])
                arbre = ast.parse(pathlib.Path(chemin).read_text(
                    encoding='utf-8'))
                gabarit = _gabarit_du_fichier(arbre)
                self.assertTrue(gabarit, f'{code} : aucun GABARIT_SORTIE')
                # la fonction qui PORTE chaque appel, pour y résoudre les `**`
                porteuses = {}
                for n in ast.walk(arbre):
                    if isinstance(n, ast.FunctionDef):
                        for sub in ast.walk(n):
                            if (isinstance(sub, ast.Call)
                                    and getattr(sub.func, 'id', None)
                                    == 'sortie_completee'):
                                porteuses.setdefault(sub, n)
                self.assertTrue(
                    porteuses,
                    f'{code} : aucun appel a `sortie_completee` releve — ce '
                    f'controle ne mesure rien sur cet agent.')
                hors = {}
                for appel, porteuse in porteuses.items():
                    for cle in self._cles_dun_appel(appel, porteuse, code):
                        if cle not in gabarit:
                            hors.setdefault(appel.lineno, []).append(cle)
                self.assertEqual(
                    hors, {},
                    f'{code} : cle(s) HORS GABARIT passees a '
                    f'`sortie_completee` — a l execution il LEVE, et le '
                    f'`except Exception` de `run` transforme la panne en '
                    f'sortie d echec MUETTE : '
                    + '; '.join(f'l.{lg} -> {sorted(v)}'
                               for lg, v in sorted(hors.items())))


if __name__ == '__main__':
    unittest.main(verbosity=2)
