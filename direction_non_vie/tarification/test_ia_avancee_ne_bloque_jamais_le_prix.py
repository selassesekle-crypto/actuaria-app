r"""CT-1..CT-7 — LE MODULE D'IA AVANCÉE EST UN CANDIDAT, JAMAIS UN
PASSAGE OBLIGÉ.

Arbitrage de la direction technique du 14/09/2026 : brancher le module
d'IA avancée (A5) dans l'arbitrage, **à condition que le système
continue de produire un prix fiable s'il tombe en panne, quelle que
soit la cause**.

Trace au site du 14/09, sept modes de panne mesurés un par un, AVANT
tout code. Quatre étaient déjà absorbés, trois TUAIENT :

    ====================================  ================  ==========
    dépendance absente (`torch`)          `success=False`   absorbé
    échec déclaré                         `result_a5=None`  absorbé
    exception interne                     `run` rattrape    absorbé
    A6 sans A5                            7 candidats, prix absorbé
    module INIMPORTABLE                   IMPORT MORT       **TUAIT**
    CONSTRUCTEUR qui lève                 PIPELINE MORT     **TUAIT**
    module qui ne REND JAMAIS             aucun délai       **TUAIT**
    ====================================  ================  ==========

Ce sceau tient les trois derniers, et le SECOND SENS des quatre autres :
un module qui va bien doit CONCOURIR.

⚠️⚠️ `CT-4` EST LE PLUS IMPORTANT DES SEPT. Fermer les trois trous en
débranchant le module les fermerait tous — et rendrait le branchement
inutile. *Un garde-fou de continuité qui n'exige pas aussi le
fonctionnement NOMINAL atteste un service qui ne rend plus rien.*

⚠️⚠️ ET `CT-7` EXISTE PARCE QUE LES SIX AUTRES ONT ÉTÉ VERTS SUR UN
CÂBLAGE CASSÉ. Ma première version posait au site un `logger.warning(…)`
dans un fichier qui n'a AUCUN logger, sur le chemin de PANNE seulement :
le cas nominal passait, les six sceaux étaient verts, et les trois
pannes que ce lot devait sauver mouraient sur un `NameError`. Mesuré
bout en bout, puis planté : le plant qui restaure ce défaut fait rougir
`CT-7` SEUL. *Un sceau qui mesure le MÉCANISME n'atteste pas le SITE où
il est câblé.*
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../')))

from direction_non_vie.tarification import pipeline_agents as PA

_RACINE = pathlib.Path(__file__).resolve().parent.parent.parent

#: la pire exécution COMPLÈTE d'A5 relevée le 14/09/2026 sur 225 runs
#: retrouvés dans les sorties de gate archivées (min 71 s, médiane 213 s,
#: p90 454 s). C'est la borne basse admissible pour le délai : au-dessous,
#: le garde-fou cesse d'être un garde-fou et devient un couperet.
_PIRE_EXECUTION_MESUREE_S = 1216.0


class CT1_UnModuleInimportableNeTuePasLOrchestrateur(unittest.TestCase):
    """CT-1 — l'import est gardé, et la cause est PUBLIÉE."""

    def test_CT1_pipeline_agents_reste_importable_sans_le_module(self):
        """⚠️ EN SOUS-PROCESSUS, ET C'EST OBLIGATOIRE : une panne d'import
        ne se simule pas dans un processus qui a déjà importé le module."""
        code = (
            'import sys\n'
            'CIBLE = "direction_non_vie.tarification.a5_deep_learning.agent"\n'
            'class Interdit:\n'
            '    def find_spec(self, nom, chemin=None, cible=None):\n'
            '        if nom == CIBLE:\n'
            '            raise ImportError("PANNE SIMULEE")\n'
            '        return None\n'
            'sys.meta_path.insert(0, Interdit())\n'
            'import direction_non_vie.tarification.pipeline_agents as pa\n'
            'print("VIVANT", pa.A5_DISPONIBLE,\n'
            '      "MOTIF" if pa.MOTIF_A5_INDISPONIBLE else "SANS_MOTIF")\n')
        r = subprocess.run(
            [sys.executable, '-B', '-c', code], cwd=str(_RACINE),
            capture_output=True, text=True, encoding='utf-8',
            errors='replace', check=False, timeout=300,
            env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONPATH': '.',
                 'PYTHONDONTWRITEBYTECODE': '1'})
        sortie = (r.stdout + r.stderr).strip()
        self.assertIn(
            'VIVANT', sortie,
            f"`pipeline_agents` n'est plus importable quand le module d'IA "
            f"avancee ne l'est pas : les CINQ autres agents meurent avec "
            f"lui, et le prix avec eux.\n{sortie[-400:]}")
        self.assertIn('False', sortie, "la sentinelle `A5_DISPONIBLE` ment")
        self.assertIn(
            'MOTIF', sortie,
            "l'indisponibilite n'est pas DITE : un module absent et un "
            "module battu rendraient le meme silence")
        print("    CT-1 SCEAU : orchestrateur vivant, indisponibilite dite")


class CT2_UneIAIndisponibleNEmpechePasLArbitrage(unittest.TestCase):
    """CT-2 — le comportement, pas seulement l'import."""

    def test_CT2_le_site_d_appel_lit_la_sentinelle_avant_de_construire(self):
        """⚠️ ON MESURE LE GESTE : si `A5_DISPONIBLE` est faux, le site ne
        doit PAS tenter de construire — sinon `AgentA5DeepLearning` vaut
        `None` et l'appel lève `TypeError` au lieu d'etre absorbé."""
        import ast
        src = pathlib.Path(PA.__file__).read_text(encoding='utf-8')
        arbre = ast.parse(src)
        garde = [n for n in ast.walk(arbre)
                 if isinstance(n, ast.If)
                 and 'A5_DISPONIBLE' in ast.unparse(n.test)]
        self.assertTrue(
            garde,
            "aucune garde `A5_DISPONIBLE` avant la construction : quand le "
            "module est absent, `AgentA5DeepLearning` vaut None et l'appel "
            "leve `TypeError`")
        #: et la construction vit bien DANS la branche « disponible »
        construit = [n for n in ast.walk(arbre)
                     if isinstance(n, ast.Call)
                     and 'AgentA5DeepLearning' in ast.unparse(n.func)]
        for appel in construit:
            dans_garde = any(
                any(x is appel for x in ast.walk(g)) for g in garde)
            self.assertTrue(
                dans_garde,
                f"la construction l.{appel.lineno} est hors de la garde "
                f"`A5_DISPONIBLE`")
        print(f"    CT-2 {len(construit)} construction(s), toutes sous la "
              f"garde `A5_DISPONIBLE`")


class CT3_UnModuleQuiNeRendJamaisEstAbandonne(unittest.TestCase):
    """CT-3 — le DÉLAI : on borne l'attente, pas le calcul."""

    def test_CT3_SCEAU_au_dela_du_delai_le_module_est_traite_en_echec(self):
        debut = time.monotonic()
        resultat, motif = PA._module_avance(lambda: time.sleep(30), 0.4)
        ecoule = time.monotonic() - debut
        self.assertIsNone(resultat, "un module abandonne ne rend rien")
        self.assertIsNotNone(
            motif, "le module a ete abandonne SANS LE DIRE : l'arbitrage "
                   "publierait une absence sans cause")
        self.assertIn('delai', motif.lower())
        self.assertLess(
            ecoule, 10.0,
            f"l'appel a attendu {ecoule:.1f} s pour un delai de 0,4 s : le "
            f"delai ne borne rien")
        print(f"    CT-3 SCEAU : abandonne en {ecoule:.2f} s, motif publie")

    def test_CT3b_une_exception_a_la_CONSTRUCTION_est_absorbee(self):
        """⚠️ LE TROU EXACT : `A5.run` a son propre filet, mais il ne couvre
        pas ce qui se passe AVANT — la construction de l'agent."""
        def _construire_qui_leve():
            raise RuntimeError('PANNE SIMULEE A LA CONSTRUCTION')
        resultat, motif = PA._module_avance(_construire_qui_leve, 30.0)
        self.assertIsNone(resultat)
        self.assertIn('RuntimeError', motif)
        self.assertIn('PANNE SIMULEE', motif)
        print("    CT-3b construction qui leve : absorbee et NOMMEE")


class CT4_UnModuleQuiVaBienCONCOURT(unittest.TestCase):
    """CT-4 — le SECOND SENS, et c'est le plus important des six."""

    def test_CT4_SCEAU_un_module_sain_rend_son_resultat_sans_motif(self):
        temoin = {'appele': 0}

        def _sain():
            temoin['appele'] += 1
            return {'success': True, 'statut_rag': 'VERT'}

        resultat, motif = PA._module_avance(_sain, 30.0)
        self.assertEqual(
            temoin['appele'], 1,
            "le module n'a PAS ete appele : fermer les trous en debranchant "
            "le module les fermerait tous, et rendrait le branchement inutile")
        self.assertEqual(resultat, {'success': True, 'statut_rag': 'VERT'})
        self.assertIsNone(
            motif, f"un module SAIN publie un motif de panne : {motif!r}")
        print("    CT-4 second sens : le module sain concourt, 0 motif")


class CT5_LeDelaiEstMesureEtNonInvente(unittest.TestCase):
    """CT-5 — l'ASSIETTE du délai lui-même."""

    def test_CT5_le_delai_par_defaut_ne_coupe_aucune_execution_mesuree(self):
        self.assertGreaterEqual(
            PA.DELAI_MAX_DL_S, _PIRE_EXECUTION_MESUREE_S,
            f"le delai par defaut ({PA.DELAI_MAX_DL_S} s) est INFERIEUR a la "
            f"pire execution legitime mesuree ({_PIRE_EXECUTION_MESUREE_S} s "
            f"sur 225 runs) : ce n'est plus un garde-fou, c'est un couperet "
            f"qui ecarterait le module a chaque gros portefeuille")
        import inspect
        defaut = inspect.signature(
            PA.pipeline_agents).parameters['delai_dl'].default
        self.assertEqual(
            defaut, PA.DELAI_MAX_DL_S,
            "le defaut de `pipeline_agents` a diverge de `DELAI_MAX_DL_S` : "
            "deux valeurs pour un seul reglage")
        print(f"    CT-5 assiette : delai {PA.DELAI_MAX_DL_S:.0f} s = "
              f"{PA.DELAI_MAX_DL_S / _PIRE_EXECUTION_MESUREE_S:.2f}x la pire "
              f"execution mesuree")


class CT6_LeFilAbandonneNeRetientPasLeProcessus(unittest.TestCase):
    """CT-6 — un fil abandonné ne doit pas bloquer la SORTIE du processus."""

    def test_CT6_le_fil_du_module_est_daemon(self):
        """⚠️⚠️ SANS CELA, LE DELAI NE SERT A RIEN. Python ne tue pas un
        fil : on cesse de l'attendre. Si ce fil n'est pas `daemon`,
        l'interpreteur le REJOINT a la sortie — et le processus se
        bloque exactement aussi longtemps que l'appel qu'on voulait
        borner. *C'est le piege d'un `ThreadPoolExecutor`, dont l'`atexit`
        rejoint ses fils.*"""
        avant = {t.ident for t in threading.enumerate()}
        PA._module_avance(lambda: time.sleep(20), 0.3)
        neufs = [t for t in threading.enumerate() if t.ident not in avant]
        nommes = [t for t in neufs if 'module_avance' in (t.name or '')]
        self.assertTrue(
            nommes, "le fil abandonne est introuvable : la mesure ne porte "
                    "sur rien")
        for t in nommes:
            self.assertTrue(
                t.daemon,
                f"le fil {t.name!r} n'est PAS daemon : l'interpreteur le "
                f"rejoindra a la sortie et le processus se bloquera autant "
                f"que l'appel qu'on venait de borner")
        print(f"    CT-6 {len(nommes)} fil(s) abandonne(s), daemon : "
              f"{[t.daemon for t in nommes]}")


class CT7_LePipelineCOMPLETRendUnPrixSansLeModule(unittest.TestCase):
    """CT-7 — LE SITE, pas le mécanisme.

    ⚠️⚠️ CE CONTRÔLE EXISTE PARCE QUE LES SIX AUTRES ONT ÉTÉ VERTS SUR UN
    CORRECTIF CASSÉ. `CT-1` à `CT-6` mesurent `_module_avance` en
    isolation et l'import dans un sous-processus : aucun n'appelle
    `pipeline_agents(...)`. Or ma première version du câblage posait un
    `logger.warning(...)` au site — et ce fichier n'a AUCUN `logger`. La
    ligne ne tirait que sur les chemins de PANNE : le cas nominal
    passait, les six sceaux étaient verts, et **les trois pannes que le
    lot devait sauver mouraient sur un `NameError`**.

    *Un sceau qui mesure le MÉCANISME n'atteste pas le SITE où il est
    câblé.* Celui-ci traverse le site pour de bon.
    """

    def test_CT7_SCEAU_module_indisponible_le_pipeline_rend_un_prix(self):
        import logging
        import warnings

        from direction_non_vie.tarification.test_plan_invariants import (
            AUTO,
            portefeuille_auto,
        )
        # ⚠️⚠️ HORS DU DEPOT, ET C'EST UNE CORRECTION. Ma premiere version
        # ecrivait sous `__file__.parent` : le run a depose des pistes
        # d'audit JSON DANS le depot public, et `git status` les proposait
        # a l'ajout. La convention du depot est `tempfile.mkdtemp` — c'est
        # ce que font `test_plan_invariants` et ses voisins.
        # *Un test qui produit des artefacts les produit hors du depot.*
        tmp = tempfile.mkdtemp(prefix='actuaria_ct7_')
        vrai = PA.A5_DISPONIBLE
        vrai_motif = PA.MOTIF_A5_INDISPONIBLE
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            precedent = logging.root.manager.disable
            logging.disable(logging.CRITICAL)
            try:
                #: le module est declare INDISPONIBLE, comme s'il n'avait
                #: pas pu s'importer -- le chemin que `CT-1` ne traverse pas
                PA.A5_DISPONIBLE = False
                PA.MOTIF_A5_INDISPONIBLE = (
                    "module d'IA avancee INDISPONIBLE a l'import : "
                    "PANNE SIMULEE PAR CT-7")
                resultat = PA.pipeline_agents(
                    portefeuille_auto(n=700), AUTO, 'auto',
                    models_path=tmp, audit_path=tmp, verbose=False,
                    generer_graphiques=False, calcul_shap=False,
                    n_epochs_dl=1)
            finally:
                PA.A5_DISPONIBLE = vrai
                PA.MOTIF_A5_INDISPONIBLE = vrai_motif
                logging.disable(precedent)
        # ⚠️⚠️ DEUX CHEMINS, ET AUCUN NE DOIT SE TAIRE. Ma première version
        # exigeait un `motif_dl` sur les TROIS cibles. Mesuré : `cout` sort
        # AVANT l'arbitrage sur un refus LÉGITIME et préexistant
        # (« Sévérité non modélisable : 97 contrat(s) à coût observé
        # (< 100) »). L'arbitrage n'a alors pas eu lieu, et il n'y a aucun
        # motif de non-participation du module à donner — le module
        # n'était même pas au programme. *Une assiette mal posée accuse un
        # comportement juste.* La bonne question n'est pas « le motif
        # est-il là ? » mais « CE QUI S'EST PASSÉ EST-IL DIT ? ».
        arbitres = 0
        for cible in ('frequence', 'cout', 'prime_pure'):
            arbitrage = getattr(resultat, cible)
            with self.subTest(cible=cible):
                self.assertIsNone(
                    arbitrage.a5,
                    "le module est declare indisponible et un resultat "
                    "d'IA avancee apparait quand meme")
                if arbitrage.a6 is None:
                    #: l'arbitrage n'a pas eu lieu -- sa cause est DITE
                    self.assertIsNotNone(
                        arbitrage.erreur,
                        f"[{cible}] aucun arbitrage ET aucune cause : le "
                        f"pipeline se tait sur une cible entiere")
                    continue
                arbitres += 1
                self.assertIsNotNone(
                    arbitrage.motif_dl,
                    f"[{cible}] l'arbitrage a eu lieu, le module n'y a pas "
                    f"concouru, et le pipeline ne DIT PAS pourquoi : une IA "
                    f"absente et une IA battue rendraient le meme silence")
                self.assertIsNotNone(
                    arbitrage.statut_rag,
                    f"[{cible}] aucun statut : le module d'IA avancee est "
                    f"reste un PASSAGE OBLIGE")
                self.assertGreater(
                    arbitrage.n_candidats, 0,
                    f"[{cible}] zero candidat en competition : le prix ne "
                    f"repose sur rien")
        #: ⚠️ ET L'ASSIETTE DE CE CONTROLE SE MESURE : si AUCUNE cible
        #: n'etait arbitree, tout ce qui precede serait vide et vert.
        self.assertGreater(
            arbitres, 0,
            "aucune des trois cibles n'a ete arbitree : ce controle "
            "attesterait sans rien surveiller")
        print(f"    CT-7 SCEAU : module indisponible -> {arbitres}/3 cible(s) "
              f"arbitree(s), " + ' '.join(
                  f"{c}={getattr(resultat, c).n_candidats}"
                  for c in ('frequence', 'cout', 'prime_pure')))


if __name__ == '__main__':
    # ⚠️ LE BLOC EN FIN DE FICHIER — constat `COLLECTE-1`, sceau `GD-1..GD-4`.
    unittest.main(verbosity=2)
