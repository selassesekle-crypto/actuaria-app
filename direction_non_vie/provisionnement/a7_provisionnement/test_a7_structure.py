# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 Ibrahim — verrous de structure : filet du lot F2
=============================================================================

 CES QUATRE TESTS NE VÉRIFIENT AUCUN CHIFFRE. Ils verrouillent ce qui rend
 les chiffres VÉRIFIABLES — et le défaut qu'ils figent avait rendu ma propre
 vérification fausse trois fois de suite.

 `config/lob_config.py` importait `from ....reglementation.segments_s2`.
 Quatre points, donc quatre niveaux au-dessus de
 `direction_non_vie.provisionnement.a7_provisionnement.config` : la forme
 n'est valide que si le paquet de tête est `direction_non_vie`, c'est-à-dire
 uniquement si la découverte des tests est lancée avec `-t .`. Sans lui, la
 racine devient `provisionnement`, l'import sort du paquet de tête,
 `a7_provisionnement/__init__.py` échoue à l'import, et unittest rend
 455 tests au lieu de 798 EN ANNONÇANT « OK ».

 Tout A7 disparaissait, et la gate restait verte. C'est le pire genre de
 défaut : il ne casse pas, il fait taire.

 T2 EST LE SEUL QUI AURAIT ATTRAPÉ CE DÉFAUT À L'ÉPOQUE — il compare les
 deux racines de découverte au lieu de raisonner sur la forme des imports.
 T1 fige la cause, T2 le symptôme ; il faut les deux, parce qu'une autre
 cause produirait le même silence.
=============================================================================
"""

import ast
import inspect
import pathlib
import typing
import unittest

#: Racine du dépôt — quatre parents au-dessus de ce fichier.
_RACINE = pathlib.Path(__file__).resolve().parents[3]
_DNV = _RACINE / 'direction_non_vie'


def _modules_python():
    """Tous les .py de `direction_non_vie`, hors caches."""
    return [p for p in _DNV.rglob('*.py') if '__pycache__' not in p.parts]


# =============================================================================
#  T1 — LA CAUSE : aucun import ne remonte au-dessus de son paquet de tête
# =============================================================================

class T1_Aucun_Import_Hors_Paquet(unittest.TestCase):

    def test_aucun_import_relatif_de_quatre_points_ou_plus(self):
        """Sur l'ARBRE SYNTAXIQUE, pas sur le texte.

        Un `from ....x import y` dans `a/b/c/d.py` ne tient que si `a` est le
        paquet de tête. Dès que la racine de découverte descend d'un cran,
        l'import sort du paquet et le module entier devient introuvable.
        La forme absolue, elle, ne dépend d'aucune racine.
        """
        fautifs = []
        for chemin in _modules_python():
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for n in ast.walk(arbre):
                if isinstance(n, ast.ImportFrom) and (n.level or 0) >= 4:
                    fautifs.append(
                        f"{chemin.relative_to(_RACINE)}:{n.lineno} "
                        f"({'.' * n.level}{n.module or ''})")
        self.assertEqual(
            fautifs, [],
            "Import relatif remontant au moins quatre niveaux — il fait "
            "dépendre le module de la racine de découverte : " + str(fautifs))
        print(f"    OK F2-1 aucun import relatif ≥ 4 points sur "
              f"{len(_modules_python())} modules de direction_non_vie")


# =============================================================================
#  T2 — LE SYMPTÔME : les deux racines de découverte voient la même chose
# =============================================================================

class T2_Decouverte_Independante_De_La_Racine(unittest.TestCase):

    @staticmethod
    def _compter(suite):
        """Compte les tests, et remonte les modules qui n'ont pas pu être lus."""
        n, casses = 0, []
        for t in suite:
            if isinstance(t, unittest.TestSuite):
                a, b = T2_Decouverte_Independante_De_La_Racine._compter(t)
                n += a
                casses += b
            elif t.__class__.__name__ == '_FailedTest':
                casses.append(t.id())
            else:
                n += 1
        return n, casses

    def test_les_deux_racines_collectent_le_meme_nombre_de_tests(self):
        """⚠️ LE SEUL TEST QUI AURAIT ATTRAPÉ LE DÉFAUT D'ORIGINE.

        Il ne suppose rien du mécanisme : il lance les deux découvertes et
        compare. N'importe quelle cause future produisant le même silence —
        un import cassé, un `__init__` qui lève — le fait échouer.
        """
        ld = unittest.TestLoader()
        sans, casses_sans = self._compter(
            ld.discover(str(_DNV), pattern='test_*.py'))
        avec, casses_avec = self._compter(
            ld.discover(str(_DNV), pattern='test_*.py',
                        top_level_dir=str(_RACINE)))

        self.assertEqual(
            casses_sans, [],
            "Des modules de test ne se chargent pas quand la découverte part "
            "de direction_non_vie sans top_level_dir : " + str(casses_sans))
        self.assertEqual(casses_avec, [], str(casses_avec))
        self.assertEqual(
            sans, avec,
            f"La découverte SANS `-t .` collecte {sans} tests, AVEC en "
            f"collecte {avec} — des tests disparaissent en silence.")
        self.assertGreater(sans, 700, "collecte anormalement basse")
        print(f"    OK F2-2 les deux racines de découverte collectent "
              f"{sans} tests, aucun module en échec")


# =============================================================================
#  T3 — `run()` REFUSE CE QU'IL NE CONNAÎT PAS
# =============================================================================

class T3_Aucun_Parametre_Avale(unittest.TestCase):

    def test_run_leve_une_erreur_sur_un_parametre_inconnu(self):
        """`run(lr_manuel=…)` au lieu de `lr_bf_manuel=` : la faute réelle.

        Elle a été commise pendant le lot F1. La signature avalait le mot-clé
        et rendait un résultat calculé sur la valeur par défaut — un chiffre
        faux, sans le moindre signal.
        """
        from direction_non_vie.provisionnement.a7_provisionnement.agent import (
            AgentA7Provisionnement)

        sig = inspect.signature(AgentA7Provisionnement.run)
        var_kw = [p.name for p in sig.parameters.values()
                  if p.kind is inspect.Parameter.VAR_KEYWORD]
        self.assertEqual(
            var_kw, [],
            f"`run()` porte à nouveau un **{var_kw} : tout mot-clé mal "
            f"orthographié redeviendra silencieux.")

        # Et la levée est réelle, pas seulement structurelle. `TypeError` est
        # levée AVANT le corps : aucun calcul n'est déclenché.
        with self.assertRaises(TypeError):
            AgentA7Provisionnement(verbose=False).run(lr_manuel=9.0)
        print("    OK F2-3 run() lève TypeError sur un mot-clé inconnu, "
              "sans **kwargs pour l'absorber")

    def test_export_pdf_non_plus_n_avale_rien(self):
        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
            export_pdf)
        var_kw = [p.name for p in inspect.signature(export_pdf).parameters.values()
                  if p.kind is inspect.Parameter.VAR_KEYWORD]
        self.assertEqual(var_kw, [], "`export_pdf` ré-avale les mots-clés inconnus")
        print("    OK F2-4 export_pdf() n'avale plus les mots-clés inconnus")


# =============================================================================
#  T4 — TOUT NOM EMPLOYÉ EST DÉFINI, ANNOTATIONS COMPRISES
# =============================================================================

class T4_Aucun_Nom_Non_Defini(unittest.TestCase):
    """Deux `F821` réels dormaient dans A7, tous deux invisibles à l'exécution."""

    def test_les_deux_noms_manquants_sont_resolus(self):
        from direction_non_vie.provisionnement.a7_provisionnement import (
            n4_best_estimate, n5_rapport)

        # `libelle_loss_ratio` était appelé par `_construire_contexte` sans
        # être importé : l'appel levait NameError, et l'appelant l'attrapait
        # dans un `except Exception` qui accusait l'API de Claude.
        self.assertTrue(hasattr(n5_rapport, 'libelle_loss_ratio'),
                        "n5_rapport appelle libelle_loss_ratio sans l'importer")
        # `Any` était employé dans deux annotations sans être importé. Sur
        # Python 3.14 (PEP 649) les annotations ne sont plus évaluées à la
        # définition ; sur Python <= 3.13 le module levait NameError à l'import.
        self.assertTrue(hasattr(n4_best_estimate, 'Any'),
                        "n4_best_estimate annote Dict[str, Any] sans importer Any")
        print("    OK F2-5 libelle_loss_ratio et Any sont résolus dans leurs "
              "modules")

    def test_toutes_les_annotations_des_modules_touches_sont_evaluables(self):
        """Le vrai verrou : on FORCE l'évaluation, que Python la diffère ou non.

        `typing.get_type_hints` résout les annotations. Sur Python 3.14 elles
        sont paresseuses (PEP 649) et un nom manquant ne se voit jamais à
        l'exécution — c'est exactement ce qui a laissé passer `Any`.
        """
        from direction_non_vie.provisionnement.a7_provisionnement import (
            n4_best_estimate, n5_rapport, n5_excel, n5_commentaire)
        from direction_non_vie.provisionnement.a7_provisionnement.config import (
            lob_config)
        from direction_non_vie.provisionnement.a7_provisionnement.n3 import (
            chain_ladder, mack, backtesting)

        modules = [n4_best_estimate, n5_rapport, n5_excel, n5_commentaire,
                   lob_config, chain_ladder, mack, backtesting]
        fautifs, verifies = [], 0
        for mod in modules:
            for nom, obj in vars(mod).items():
                if not (inspect.isfunction(obj) or inspect.isclass(obj)):
                    continue
                if getattr(obj, '__module__', None) != mod.__name__:
                    continue
                cibles = [obj] if inspect.isfunction(obj) else [
                    m for m in vars(obj).values() if inspect.isfunction(m)]
                for cible in cibles:
                    try:
                        typing.get_type_hints(cible)
                        verifies += 1
                    except NameError as e:
                        fautifs.append(f'{mod.__name__}.{nom} : {e}')
                    except Exception:
                        pass          # types non résolubles sans exécution
        self.assertEqual(fautifs, [],
                         "Annotation citant un nom non défini : " + str(fautifs))
        print(f"    OK F2-6 {verifies} signatures évaluées sur "
              f"{len(modules)} modules, aucun nom non défini")


if __name__ == '__main__':
    unittest.main(verbosity=2)
