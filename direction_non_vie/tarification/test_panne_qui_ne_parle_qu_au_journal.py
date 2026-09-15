"""UNE PANNE QUI NE PARLE QU'AU JOURNAL EST UNE PANNE QUE PERSONNE NE LIT.

⚠️⚠️ TROIS CONSTATS, UNE SEULE CAUSE. `A1-2`, `A5-1` et `PIPE-4` ont ete
classes separement par le 5e audit ; mesures au site, ils disent la meme
chose : **le canal par lequel un echec sort n'atteint aucun lecteur.**

  `A1-2`   `except Exception: pass` rendait une config PRESENTE MAIS
           ILLISIBLE rigoureusement indiscernable d'une config ABSENTE.
           Mesure : meme dict rendu, meme unique ligne de journal. *Une
           faute de frappe deplacait SILENCIEUSEMENT tous les chemins de
           donnees vers `/tmp/actuaria`.*

  `A5-1`   les HUIT constructions de figures (`_generer_graphiques` G1..G4,
           `_graphiques_validation_dl` G1..G4) etaient gardees par un
           `except ...: logger.warning(...)` **et rien d'autre**. Le
           document sortait avec trois graphiques au lieu de quatre, et
           aucun lecteur ne pouvait savoir qu'un quatrieme avait ete tente.

  `PIPE-4` `tarifer()` rendait 5 / 18 / 4 cles selon le chemin -- l'union
           en fait 20, le chemin le plus pauvre en perdait SEIZE. Releve :
           **119 lectures** dans le depot portent sur une de ces cles, dont
           cinq en production, dans la table de detail du rapport signe.

*Le journal n'est pas une surface signee.* La parade est la meme dans les
trois cas : **le fait sort du journal et entre dans ce que l'appelant
recoit** -- un niveau ERREUR distinct pour `A1-2`, une cle declaree au
gabarit pour `A5-1` et `PIPE-4`.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""
from __future__ import annotations

import ast
import io
import logging
import os
import pathlib
import sys
import tempfile
import unittest
import warnings

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

from core.plan_tarifaire import PlanTarifaire
from direction_non_vie.tarification.a1_ingestion.agent import (
    _charger_config,
)
from direction_non_vie.tarification.pipeline_tarifaire import (
    GABARIT_TARIF,
    pipeline_complet,
)
from direction_non_vie.tarification.test_plan_invariants import (
    portefeuille_auto,
)

_A5 = pathlib.Path(_ICI) / 'a5_deep_learning' / 'agent.py'
_PIPE = pathlib.Path(_ICI) / 'pipeline_tarifaire.py'
_BUILDERS = ('_generer_graphiques', '_graphiques_validation_dl')


def _journal_de(fn, *a, **kw):
    """Ce que le journal DIT pendant cet appel, niveaux compris."""
    flux = io.StringIO()
    poste = logging.StreamHandler(flux)
    poste.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
    racine = logging.getLogger()
    anciens, niveau = list(racine.handlers), racine.level
    racine.handlers = [poste]
    racine.setLevel(logging.DEBUG)
    precedent = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    try:
        return fn(*a, **kw), flux.getvalue()
    finally:
        racine.handlers, racine.level = anciens, niveau
        logging.disable(precedent)


# =============================================================================
#  A1-2 — UNE CONFIG ILLISIBLE N'EST PAS UNE CONFIG ABSENTE
# =============================================================================

class TestConfigIllisibleSeDistingue(unittest.TestCase):
    """⚠️ PAR EXECUTION, sur deux fichiers REELS construits pour l'occasion."""

    def _deux_cas(self, dossier):
        illisible = os.path.join(dossier, 'actuaria_config.json')
        with open(illisible, 'w', encoding='utf-8') as fh:
            fh.write('{"base_path": "/donnees/prod",')      # JSON tronque
        return os.path.join(dossier, 'nexiste_pas.json'), illisible

    def test_PJ1_les_deux_etats_ne_disent_PAS_la_meme_chose(self):
        with tempfile.TemporaryDirectory() as dossier:
            absent, illisible = self._deux_cas(dossier)
            _, j_a = _journal_de(_charger_config, absent)
            _, j_i = _journal_de(_charger_config, illisible)
        self.assertNotEqual(
            j_a.strip(), j_i.strip(),
            "une config PRESENTE mais ILLISIBLE et une config ABSENTE "
            "produisent le MEME journal : elles sont indiscernables, et "
            "c'est tout le constat A1-2")
        self.assertIn(
            'ERROR', j_i,
            "l'echec de LECTURE n'est pas emis au niveau ERREUR : il se "
            "noie dans les avertissements de routine")
        self.assertNotIn(
            'ERROR', j_a,
            "une config simplement ABSENTE emet une ERREUR : le niveau ne "
            "distingue plus rien")
        print('    PJ-1 config illisible : ERREUR nommee ; config absente : '
              'avertissement seul')

    def test_PJ2_SECOND_SENS_le_dict_rendu_reste_le_MEME(self):
        """⚠️⚠️ ON NE LEVE PAS, ET C'EST UNE DECISION DECLAREE : la config
        n'est qu'un jeu de chemins, un run sans elle reste possible. Ce
        second sens interdit qu'on « corrige » A1-2 en changeant le
        comportement -- ce qui casserait tous les appelants."""
        with tempfile.TemporaryDirectory() as dossier:
            absent, illisible = self._deux_cas(dossier)
            cfg_a, _ = _journal_de(_charger_config, absent)
            cfg_i, _ = _journal_de(_charger_config, illisible)
        self.assertEqual(
            cfg_a, cfg_i,
            'le dict rendu a change selon la cause : un appelant qui lisait '
            '`base_path` recoit desormais autre chose')
        self.assertTrue(cfg_i.get('base_path'),
                        'la config de repli ne porte plus de `base_path`')
        print('    PJ-2 second sens : meme dict rendu, seul le JOURNAL '
              'distingue les deux causes')

    def test_PJ3_aucun_except_MUET_ne_subsiste_dans_A1(self):
        """⚠️ L'assiette du constat : `pass` seul dans un `except`."""
        arbre = ast.parse((pathlib.Path(_ICI) / 'a1_ingestion' / 'agent.py')
                          .read_text(encoding='utf-8'))
        muets = [n.lineno for n in ast.walk(arbre)
                 if isinstance(n, ast.ExceptHandler)
                 and all(isinstance(x, ast.Pass) for x in n.body)]
        self.assertEqual(
            muets, [],
            f'`except ...: pass` a a1:{muets} — une panne y disparait sans '
            f'laisser la moindre trace, pas meme au journal')
        print('    PJ-3 A1 : 0 `except` muet')


# =============================================================================
#  A5-1 — UNE FIGURE QUI ECHOUE LE DIT DANS LE RESULTAT
# =============================================================================

class TestFiguresAbsentesDeclarees(unittest.TestCase):

    def test_PJ4_les_HUIT_gardes_de_figure_ecrivent_dans_le_resultat(self):
        """⚠️⚠️ L'ASSIETTE SE DERIVE, elle n'est pas comptee a la main : on
        prend TOUS les `except` des deux constructeurs qui journalisent, et
        on exige que chacun pose aussi sa trace. Une NEUVIEME figure ajoutee
        demain entre dans la mesure sans que ce test change."""
        arbre = ast.parse(_A5.read_text(encoding='utf-8'))
        parlants, muets = [], []
        for n in ast.walk(arbre):
            if not (isinstance(n, ast.FunctionDef) and n.name in _BUILDERS):
                continue
            for essai in ast.walk(n):
                if not isinstance(essai, ast.Try):
                    continue
                for h in essai.handlers:
                    corps = ast.unparse(
                        ast.Module(body=h.body, type_ignores=[]))
                    if 'logger' not in corps:
                        continue
                    (parlants if 'figures_absentes' in corps
                     else muets).append(h.lineno)
        self.assertEqual(
            muets, [],
            f'a5:{muets} : la figure echoue, le journal le sait, et le '
            f'RESULTAT ne le sait pas — le document sortira avec une figure '
            f'de moins sans le dire')
        self.assertGreaterEqual(
            len(parlants), 8,
            f'seulement {len(parlants)} garde(s) de figure relevee(s) : '
            f'l assiette de ce controle s est vidée')
        print(f'    PJ-4 {len(parlants)} gardes de figure declarent leur '
              f'echec, 0 muette')

    def test_PJ5_la_cle_est_AU_GABARIT_donc_presente_en_echec_aussi(self):
        """⚠️ Sans cela, un A5 en echec n'aurait PAS la cle, et son lecteur
        poserait un litteral — le defaut que la famille (6) vient de fermer."""
        from direction_non_vie.tarification.a5_deep_learning.agent import (
            GABARIT_SORTIE,
        )
        self.assertIn('figures_absentes', GABARIT_SORTIE)
        self.assertEqual(
            GABARIT_SORTIE['figures_absentes'], {},
            "la forme vide doit etre `{}` — « aucune figure n'a echoue » — "
            "et non `None`, qui dirait « on n'a pas regarde »")
        print('    PJ-5 `figures_absentes` au gabarit, forme vide `{}`')

    def test_PJ6_elle_est_REMISE_A_ZERO_a_chaque_run(self):
        """⚠️ Un agent reutilise publierait sinon l'echec du run precedent.
        On lit le code de `run`, faute de pouvoir lancer deux runs DL ici."""
        arbre = ast.parse(_A5.read_text(encoding='utf-8'))
        remises = []
        for n in ast.walk(arbre):
            if not (isinstance(n, ast.FunctionDef) and n.name == 'run'):
                continue
            for s in ast.walk(n):
                if (isinstance(s, ast.Assign) and len(s.targets) == 1
                        and isinstance(s.targets[0], ast.Attribute)
                        and s.targets[0].attr == 'figures_absentes'):
                    remises.append(s.lineno)
        self.assertTrue(
            remises,
            '`run` ne remet pas `self.figures_absentes` a zero : un second '
            'run republierait les figures manquantes du premier')
        print(f'    PJ-6 remise a zero dans `run`, l.{remises}')


# =============================================================================
#  PIPE-4 — `tarifer()` REND LES MEMES CLES SUR SES TROIS CHEMINS
# =============================================================================

class TestTariferRendLesMemesCles(unittest.TestCase):
    """⚠️ PAR EXECUTION pour les deux chemins qu'un contrat peut emprunter,
    et par relevé pour le troisième — et **ce controle le dit**."""

    @classmethod
    def setUpClass(cls):
        warnings.filterwarnings('ignore')
        logging.disable(logging.CRITICAL)
        plan = PlanTarifaire.depuis_yaml(
            os.path.join(_RACINE, 'plans', 'auto.yaml'))
        df = portefeuille_auto(1200, 11).reset_index(drop=True)
        cls.plan, cls.tarif = plan, pipeline_complet(df, plan)
        cls.sain = {c: df.iloc[0][c] for c in df.columns
                    if c in plan.colonnes_attendues()}

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_PJ7_succes_et_refus_rendent_EXACTEMENT_le_gabarit(self):
        sale = dict(self.sain)
        for f in self.plan.facteurs:
            if getattr(f, 'nom', None) in sale:
                sale[f.nom] = 'valeur_illisible_###'
                break
        succes = self.tarif.tarifer(dict(self.sain))
        refus = self.tarif.tarifer(sale)
        self.assertTrue(succes['success'], succes.get('erreur'))
        self.assertFalse(refus['success'],
                         'le contrat sale devait etre REFUSE : ce controle '
                         'ne mesure plus le chemin qu il decrit')
        for nom, sortie in (('succes', succes), ('refus', refus)):
            with self.subTest(chemin=nom):
                self.assertEqual(
                    sorted(sortie), sorted(GABARIT_TARIF),
                    f'{nom} : manquantes '
                    f'{sorted(set(GABARIT_TARIF) - set(sortie))} ; en trop '
                    f'{sorted(set(sortie) - set(GABARIT_TARIF))}')
        print(f'    PJ-7 succes et refus : {len(GABARIT_TARIF)} cles '
              f'identiques')

    def test_PJ8_un_prix_NON_CALCULE_vaut_None_jamais_zero(self):
        """⚠️⚠️ *Un zero se lit comme une mesure.* C'est la difference entre
        « ce contrat coute 0 EUR » et « ce contrat n'a pas ete tarife »."""
        sale = dict(self.sain)
        for f in self.plan.facteurs:
            if getattr(f, 'nom', None) in sale:
                sale[f.nom] = 'valeur_illisible_###'
                break
        refus = self.tarif.tarifer(sale)
        for cle in ('prime_pure', 'prime_commerciale_ht', 'prime_ttc',
                    'frequence_annuelle', 'cout_moyen'):
            self.assertIsNone(
                refus[cle],
                f'{cle} vaut {refus[cle]!r} sur un contrat NON TARIFE : une '
                f'valeur y affirmerait un prix que personne n a calcule')
        print('    PJ-8 contrat refuse : les 5 grandeurs de prix a `None`')

    def test_PJ9_anomalies_contrat_dit_LEQUEL_des_trois_sens(self):
        """⚠️ TROIS SENS, ET LA FORME VIDE EN MENTIRAIT UN. `[]` = on a
        regarde et il n'y a rien ; `None` = on n'a pas pu regarder ; une
        liste = voici ce qu'on a trouve. Un gabarit a `[]` ferait dire au
        chemin d'exception qu'il a controle un contrat sain."""
        succes = self.tarif.tarifer(dict(self.sain))
        self.assertEqual(succes['anomalies_contrat'], [],
                         'le chemin de SUCCES doit dire « aucune anomalie », '
                         'pas « non mesure »')
        self.assertIsNone(
            GABARIT_TARIF['anomalies_contrat'],
            'la forme vide du gabarit doit rester `None` : sur le chemin '
            "d'exception, le controle n'a pas eu lieu")
        print('    PJ-9 `anomalies_contrat` : [] au succes, None au gabarit')

    def test_PJ10_le_chemin_d_EXCEPTION_passe_lui_aussi_par_le_gabarit(self):
        """⚠️⚠️ CE CONTROLE-CI EST STRUCTUREL, ET JE LE DIS. Faire lever
        `tarifer()` demanderait de casser un interne, donc de figer un
        detail d'implementation. On verifie donc que `tarifer` ne porte
        AUCUN `return {...}` brut et que ses trois sorties passent par
        `sortie_completee`.

        *Un controle structurel qui se declare tel vaut mieux qu'un controle
        par execution qui n'a pas lieu.*
        """
        arbre = ast.parse(_PIPE.read_text(encoding='utf-8'))
        bruts, complets = [], 0
        for n in ast.walk(arbre):
            if not (isinstance(n, ast.FunctionDef) and n.name == 'tarifer'):
                continue
            for s in ast.walk(n):
                if not isinstance(s, ast.Return):
                    continue
                if isinstance(s.value, ast.Dict):
                    bruts.append(s.lineno)
                elif (isinstance(s.value, ast.Call)
                      and getattr(s.value.func, 'id', None)
                      == 'sortie_completee'):
                    complets += 1
        self.assertEqual(
            bruts, [],
            f'`tarifer` rend un dict BRUT a pipeline_tarifaire:{bruts} — ce '
            f'chemin peut publier un jeu de cles different des autres')
        self.assertGreaterEqual(
            complets, 3,
            f'seulement {complets} sortie(s) par le gabarit : les trois '
            f'chemins de `tarifer` doivent y passer')
        print(f'    PJ-10 `tarifer` : 0 `return {{...}}` brut, {complets} '
              f'sorties par le gabarit')


if __name__ == '__main__':
    unittest.main(verbosity=2)
