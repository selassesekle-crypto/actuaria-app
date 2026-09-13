r"""
==============================================================================
  UNE CONSOLE QUI NE SAIT PAS ECRIRE NE DOIT PAS RENDRE UN VERDICT FAUX
==============================================================================

⚠️⚠️ `ENC-1` -- ET L'AUDITEUR N'AVAIT ECRIT AUCUN CORRECTIF. Il le dit :
*<< le remede est une ligne de documentation a la racine, pas un
changement de code [...] il n'est pas dans le patch livre, et il n'a donc
pas subi les trois verifications >>*. Ce lot est donc de la CONCEPTION.

LE DEFAUT. Sur une console cp1252 -- le defaut de Windows en francais --
`py -B -m unittest` rend `FAILED (errors=10)` sur un arbre PROPRE. La
cause n'est pas un calcul : ce sont les `print` des controles eux-memes,
qui portent des caracteres que cp1252 ne sait pas ecrire. *Le calcul
etait juste, c'est l'affichage qui a echoue -- et un developpeur qui lit
dix erreurs qui n'en sont pas cesse de croire le harnais.*

⚠️⚠️ UNE LIGNE DE DOCUMENTATION NE SE VERIFIE PAS, ET C'EST LA TOUTE LA
QUESTION DE CONCEPTION. Le remede decrit est une page a la racine ; une
page ne rougit jamais. Ce fichier la REND MESURABLE : il relance un
processus ENFANT a sortie cp1252 et regarde ce qui s'y passe vraiment.
Les trois faits que le README affirme y sont VERIFIES, pas cites :

    1. un `print` nu d'un caractere non representable LEVE      (EN-1)
    2. `afficher_sans_echouer` ne leve PAS et rend un substitut (EN-2)
    3. `scripts/gate.py` pose `PYTHONUTF8=1` lui-meme           (EN-3)

*Si l'un des trois cessait d'etre vrai, le README deviendrait faux -- et
c'est ce controle qui le dirait.*

⚠️ L'EXPOSITION RESIDUELLE EST CHIFFREE, PAS RACONTEE : 32 fichiers de
test et 418 sites de `print` du perimetre portent au moins un caractere
non representable en cp1252 (mesure du 13/09/2026, par arbre syntaxique,
sur les seuls arguments de `print`). `EN-4` la remesure a chaque
execution : *une phrase de portee se mesure comme un chiffre.*
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import subprocess
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

#: Un caractere que cp1252 ne sait pas ecrire, et que le depot emploie.
_SIGNE = '⚠'


def _enfant(code: str):
    """Un processus a sortie cp1252, quelle que soit la console d'ici.

    ⚠️⚠️ `PYTHONIOENCODING` ET `PYTHONUTF8` SONT RETIRES DE L'HERITAGE.
    Sans cela, la mesure dependrait de la console qui lance le test -- et
    sous la gate, qui pose `PYTHONUTF8=1`, elle mesurerait l'inverse de ce
    qu'elle croit mesurer. *Un controle dont le resultat depend de son
    lanceur n'atteste rien.*"""
    env = {k: v for k, v in os.environ.items()
           if k not in ('PYTHONIOENCODING', 'PYTHONUTF8')}
    env['PYTHONIOENCODING'] = 'cp1252'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONPATH'] = str(_RACINE)
    #: ⚠️ `check=False` EXPLICITE, ET C'EST LE COEUR DU CONTROLE : on
    #: ATTEND qu'un des enfants echoue -- lever ici transformerait la
    #: mesure du defaut en panne du controle.
    r = subprocess.run([sys.executable, '-B', '-c', code], cwd=str(_RACINE),
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', env=env, timeout=120, check=False)
    return r.returncode, r.stdout + r.stderr


def _non_cp1252(s: str) -> bool:
    try:
        s.encode('cp1252')
        return False
    except (UnicodeEncodeError, LookupError):
        return True


class TestUneConsoleQuiNeMentPas(unittest.TestCase):

    def test_EN1_le_defaut_est_REEL_un_print_nu_LEVE(self):
        """⚠️⚠️ LA PREMISSE DU README, MESUREE. Si ce `print` cessait de
        lever, la page a la racine mettrait en garde contre un danger qui
        n'existe plus -- et une consigne qui ne sert a rien finit par etre
        ignoree quand elle sert."""
        code, sortie = _enfant(f"print({_SIGNE!r} + ' avertissement')")
        self.assertNotEqual(
            code, 0,
            "un `print` non representable ne leve plus sur une console "
            "cp1252 : la mise en garde du README n'a plus d'objet")
        self.assertIn(
            'UnicodeEncodeError', sortie,
            f"l'echec n'est pas celui qu'on decrit : {sortie[-200:]}")
        print(f"    EN-1 : `print` nu sur cp1252 -> code {code}, "
              f"UnicodeEncodeError")

    def test_EN2_le_cote_CHAINE_est_bien_FERME(self):
        """⚠️⚠️ CE QUI PROTEGE DEJA LA PRODUCTION, ET QUI NE DOIT PAS SE
        DEFAIRE. `afficher_sans_echouer` est appele dans les SIX agents :
        sur la meme console, un agent qui affiche un caractere non
        representable ecrit un substitut et CONTINUE. Sans lui, A3
        basculait de `success=True / VERT` a `success=False / ROUGE` -- un
        defaut d'affichage qui changeait un verdict."""
        code, sortie = _enfant(
            'from core.sortie_console import afficher_sans_echouer\n'
            f"ok = afficher_sans_echouer(lambda: print({_SIGNE!r} + ' ok'))\n"
            "print('rendu sans lever :', ok)")
        self.assertEqual(
            code, 0,
            f"`afficher_sans_echouer` LEVE sur une console cp1252 : le cote "
            f"chaine n'est plus ferme.\n{sortie[-300:]}")
        self.assertIn('rendu sans lever : True', sortie,
                      f'le rendu a echoue : {sortie[-200:]}')
        #: ⚠️ ET LES SIX AGENTS L'EMPLOIENT ENCORE -- un garde-fou qu'on
        #: cesse d'appeler ne protege plus rien.
        agents = [p for p in sorted(
            (_RACINE / 'direction_non_vie' / 'tarification').rglob('agent.py'))
            if 'afficher_sans_echouer' in p.read_bytes().decode('utf-8')]
        self.assertGreaterEqual(
            len(agents), 6,
            f'seulement {len(agents)} agent(s) appellent '
            f'`afficher_sans_echouer` : {[p.parent.name for p in agents]}')
        print(f"    EN-2 : `afficher_sans_echouer` tient sur cp1252, "
              f"{len(agents)} agents l emploient")

    def test_EN3_la_gate_officielle_pose_la_variable_ELLE_MEME(self):
        """⚠️⚠️ LU DANS LE FICHIER, PAS CRU. La gate est immune parce
        qu'elle pose `PYTHONUTF8=1` dans l'environnement qu'elle donne a
        ses enfants -- si elle cessait, tout le harnais deviendrait
        dependant de la console qui le lance."""
        src = (_RACINE / 'scripts' / 'gate.py').read_bytes().decode('utf-8')
        poses = [n for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Dict) and 'PYTHONUTF8' in ast.unparse(n)]
        self.assertTrue(
            poses,
            "`scripts/gate.py` ne pose plus `PYTHONUTF8` : la gate n'est "
            "plus immune a la console qui la lance")
        env = ast.unparse(poses[0])
        self.assertIn("'PYTHONUTF8': '1'", env,
                      f'la variable est posee a une autre valeur : {env[:90]}')
        print(f"    EN-3 : la gate pose PYTHONUTF8=1 (l.{poses[0].lineno})")

    def test_EN4_l_exposition_residuelle_est_CHIFFREE(self):
        """⚠️ UNE PHRASE DE PORTEE SE MESURE COMME UN CHIFFRE. Le README
        annonce 32 fichiers et 418 sites : ce controle les recompte, par
        arbre syntaxique et sur les seuls arguments de `print`. Il ne fige
        pas le chiffre -- il refuse qu'il tombe a ZERO sans que la page
        soit relue, car alors la mise en garde n'aurait plus d'objet."""
        fichiers = sites = 0
        for p in sorted(_RACINE.rglob('test_*.py')):
            s = str(p).replace('\\', '/')
            if '__pycache__' in s:
                continue
            if not ('/direction_non_vie/tarification/' in s or '/core/' in s):
                continue
            try:
                arbre = ast.parse(p.read_bytes().decode('utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue
            n = sum(1 for x in ast.walk(arbre)
                    if isinstance(x, ast.Call)
                    and getattr(x.func, 'id', None) == 'print'
                    and any(_non_cp1252(y.value) for y in ast.walk(x)
                            if isinstance(y, ast.Constant)
                            and isinstance(y.value, str)))
            if n:
                fichiers += 1
                sites += n
        self.assertGreater(
            sites, 0,
            "plus aucun `print` du perimetre ne porte de caractere non "
            "representable en cp1252 : la mise en garde du README n'a plus "
            "d'objet et la page doit etre relue")
        print(f"    EN-4 : {fichiers} fichier(s), {sites} site(s) de `print` "
              f"non representables en cp1252")

    def test_EN5_la_page_d_accueil_EXISTE_et_nomme_la_variable(self):
        """⚠️ LE GARDE-FOU DE DOCUMENTATION, ET IL SE SAIT TEL. Il ne
        remplace pas `EN-1` a `EN-4`, qui lisent des COMPORTEMENTS ; il
        verifie que ce qu'ils mesurent est bien DIT a l'endroit ou un
        lecteur le cherchera. *Le constat `ENC-1` n'est pas un defaut de
        calcul, c'est un defaut d'accueil.*"""
        readme = _RACINE / 'README.md'
        self.assertTrue(
            readme.is_file(),
            "aucun `README.md` a la racine : le constat `ENC-1` porte "
            "precisement sur l'absence d'accueil")
        texte = readme.read_bytes().decode('utf-8')
        for attendu in ('PYTHONUTF8=1', 'cp1252', 'sortie_console',
                        'gate.py'):
            self.assertIn(
                attendu, texte,
                f"le README ne nomme pas {attendu!r} : le lecteur ne peut "
                f"pas agir")
        #: ⚠️ ET IL NE PORTE NI NOM DE PERSONNE NI CHEMIN LOCAL -- le depot
        #: est PUBLIC, et une page d'accueil est ce qu'on lit en premier.
        import re
        self.assertIsNone(
            re.search(r'[A-Za-z]:[\\/]+Users[\\/]+', texte),
            'le README porte un chemin local')
        print(f"    EN-5 : README.md present, {len(texte)} caracteres, "
              f"4 / 4 reperes nommes")


if __name__ == '__main__':
    unittest.main(verbosity=2)
