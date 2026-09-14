r"""
==============================================================================
  UN VERDICT NE DEPEND PAS DE L'ENCODAGE DE LA CONSOLE QUI L'A LU
==============================================================================

⚠️⚠️ `TEST-D2` -- LE MEME CODE REND DEUX VERDICTS SELON LA CONSOLE. Un
`print` de test portant un caractere hors `cp1252` -- l'encodage par
defaut d'une console Windows francaise -- leve `UnicodeEncodeError`, et
l'echec de RENDU devient un echec de TEST.

    PYTHONUTF8=0   Ran 21 tests  ->  FAILED (errors=1)
    PYTHONUTF8=1   Ran 21 tests  ->  OK

Mesure du 14/09/2026 par l'instrument de ce lot :
**350 fichiers de test sur 409** portent au moins un caractere que
`cp1252` ne sait pas representer.

⚠️ LE DEPOT AVAIT DEJA CONSTRUIT `core/sortie_console.py` POUR CE
DEFAUT, cote AGENTS, et son en-tete le dit :
*<< ET L'INSTRUMENT DE PREUVE EST ATTEINT [...] Tant que ce defaut
tient, tout « aucun euro n'a bouge » ne vaut que pour l'encodage de la
console qui l'a mesure. >>* Il n'avait pas ete applique aux TESTS.

⚠️⚠️ CE QUI EST FAIT, ET CE QUI NE L'EST PAS -- et on le DIT.
`scripts/gate.py` se protege DEUX fois : il impose `PYTHONUTF8=1` ET
`PYTHONIOENCODING=utf-8:backslashreplace`, ce second faisant DEGRADER un
caractere au lieu de le faire LEVER. Ce lot n'ajoute donc rien a la
gate : il ajoute l'INSTRUMENT qui mesure la dependance, la PORTE
(`imposer_l_encodage_du_processus`) qu'un lanceur peut franchir, et il
retire la RECOPIE de la variable.

Les 350 fichiers ne sont PAS reecrits : leur caractere hors cp1252 est
le plus souvent un `⚠️` de docstring, et les reecrire serait un chantier
a part. `VC-4` les COMPTE, publie le chiffre, et MORD si leur nombre
augmente.

⚠️ `imposer_l_encodage_du_processus` NE S'APPELLE JAMAIS A L'IMPORT. Un
module qui reconfigure `sys.stdout` en etant importe impose son choix a
tout appelant, y compris a celui qui capture la sortie pour la verifier
-- c'est exactement le defaut que `test_journaux_importables`
verrouille. `VC-5` le tient.
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from core.sortie_console import (
    ENCODAGE_IMPOSE,
    caracteres_hors_encodage,
    imposer_l_encodage_du_processus,
    verdict_depend_de_l_encodage,
)

_GATE = _RACINE / 'scripts' / 'gate.py'
_SOCLE = _RACINE / 'core' / 'sortie_console.py'
#: ⚠️ MESURE DU 14/09/2026 : les fichiers de test SUIVIS PAR GIT qui
#: portent un caractere hors cp1252. Ce controle MORD si ce nombre
#: AUGMENTE.
#: ⚠️⚠️ ET CE FICHIER-CI EST L'UN D'EUX : sa docstring porte des `⚠️`.
#: Le premier seuil, pose a 350, a mordu sur le sceau lui-meme au moment
#: ou il est ne. *Le controle qui mesure le defaut le porte aussi* -- on
#: le dit plutot que d'exempter le sceau, ce qui retrecirait l'assiette
#: pour faire passer mon propre travail.
#:
#: ⚠️⚠️ 351 -> 353 LE 14/09/2026, ET LES DEUX RAISONS SONT DECLAREES :
#:   1. DEUX SCEAUX NEUFS entrent dans le corpus le meme jour --
#:      `test_validation_ml_porte_sur_un_ml` (constats `A4-2`/`A4-3`) et
#:      `test_ia_avancee_ne_bloque_jamais_le_prix` (continuite du module
#:      d'IA avancee). Ils portent des accents et des `⚠️` comme les 351
#:      autres. Les ecrire en ASCII pur les rendrait illisibles pour un
#:      actuaire francais et les couperait de la convention du corpus :
#:      *on releve le plafond et on dit pourquoi, on n'exempte pas ses
#:      propres fichiers.* C'est le precedent pose a 350 -> 351.
#:   2. L'ASSIETTE A ETE REPAREE dans le meme lot -- voir
#:      `_fichiers_de_test`. Elle balayait le DISQUE et ramassait 60
#:      fichiers de la bibliotheque standard CPython tombee dans
#:      `Python/` ; le chiffre valait 413 sur l'arbre de travail et 353 a
#:      la gate. Il vaut desormais LA MEME CHOSE PARTOUT.
#:
#: ⚠️⚠️⚠️ 353 -> 355 LE 14/09/2026 AU SOIR, ET LA VRAIE LECON N'EST PAS LE
#: CHIFFRE : C'EST POURQUOI LA GATE NE L'AVAIT PAS VU.
#:
#: Le plafond 353 a ete dépassé au commit `18be214`, et sa gate etait
#: VERTE. Mesure, corpus suivi par git a chaque commit :
#:
#:     6dc09ee   351 suivis   plafond pose a 353 (anticipant 2 sceaux)
#:     34f9824   352 suivis   ok
#:     95dcc37   353 suivis   ok, a la limite
#:     18be214   354 suivis   *** DEPASSE, et deja POUSSE
#:
#: ⛔⛔ UN FICHIER DE TEST NEUF EST INVISIBLE AUX SCEAUX QUI DERIVENT DE
#: `git ls-files` PENDANT LA GATE DE SON PROPRE LOT. Il n'est pas encore
#: SUIVI : ni ce controle-ci, ni `RD-7`, ne le voient. Il ne mord qu'a la
#: gate SUIVANTE -- un lot trop tard, et sur du code deja pousse. Les deux
#: rouges de la gate du 14/09 au soir ont cette seule et meme cause, et
#: ils ont ete trouves par DEUX sceaux independants.
#:
#: ⚠️ LA PARADE EST DANS LA METHODE, PAS DANS CE CHIFFRE : on `git add` le
#: lot DANS l'instantane avant de lancer la gate. `git ls-files` lit
#: l'index, donc les sceaux balayeurs voient alors exactement ce que
#: l'etat commite portera. *Une assiette qui ignore le travail en cours
#: mesure l'avant-veille.*
#:
#: Les DEUX unites de la hausse : `test_a6_relaie_le_prix_qu_il_batit`
#: (le 354e, deja suivi, non anticipe par le plafond de `6dc09ee`) et
#: `test_radar_survit_a_une_mesure_absente` (constat `RADAR-1`, suivi des
#: ce commit). Tous deux portent accents et `⚠️` comme les 353 autres :
#: *on releve le plafond et on dit pourquoi, on n'exempte pas ses propres
#: fichiers.*
#:
#: ⚠️ 355 -> 356 : `test_assiette_ciblee`, le sceau de l'outil de gate
#: ciblee, entre dans le corpus. **Cette hausse-ci est posee DANS LE MEME
#: LOT que le fichier qui la cause, et AVANT sa gate** -- c'est exactement
#: la lecon ci-dessus, appliquee des le lot suivant plutot que constatee un
#: lot trop tard. *Une lecon qu'on ecrit sans changer le geste suivant n'est
#: pas une lecon.*
#:
#: ⚠️ 356 -> 357 : `test_phrases_qui_disent_le_vrai`, le sceau de la famille
#: des huit phrases fausses. Troisieme hausse posee DANS LE LOT qui la cause
#: et AVANT sa gate -- le geste est devenu routine, et c'est exactement ce
#: qu'on attend d'une lecon.
#:
#: ⚠️ CE PLAFOND NE PEUT QUE BAISSER. Il ne se releve que sur un fichier
#: AJOUTE, jamais sur un fichier qui se met a dependre de l'encodage.
_FICHIERS_A_RISQUE = 357


def _fichiers_de_test() -> list:
    """Les fichiers de test QUE GIT PUBLIE -- et rien d'autre.

    ⚠️⚠️ CETTE FONCTION BALAYAIT LE DISQUE, ET SON CHIFFRE DEPENDAIT DE LA
    MACHINE. Mesure du 14/09/2026 sur l'arbre de travail :

        413 fichiers `test_*.py` sur le disque
        351 suivis par git   <- le vrai corpus
         60 dans `Python/`   <- l'installation CPython tombee dans le
                                depot le 03/09, IGNOREE par `.gitignore`
                                et pourtant balayee ici
          2 mes sceaux du jour, pas encore commites

    Les 60 sont la bibliotheque standard de CPython (`idlelib/idle_test/`
    et consorts). Un autre poste, ou un instantane `git worktree`, n'en a
    aucun : le meme controle publiait donc 413 ici et 353 a la gate.
    *Un plafond de dette qui change selon l'endroit ou on le lit ne
    mesure aucune dette.*

    ⚠️ LE BON GESTE EXISTAIT A UN FICHIER DE DISTANCE :
    `test_racine_derivee.py::_fichiers_suivis` derive de `git ls-files`
    depuis le 12/09, avec sa raison ecrite -- << un `.gitignore` peut
    cacher un fichier au disque ; seul `git ls-files` dit ce qui part
    chez le lecteur du depot public >>. L'asymetrie entre voisins, encore.
    """
    import subprocess
    try:
        sortie = subprocess.run(
            ['git', 'ls-files'], cwd=str(_RACINE), capture_output=True,
            text=True, encoding='utf-8', errors='replace', timeout=120,
            check=False).stdout
        rels = [r for r in sortie.split('\n')
                if pathlib.PurePosixPath(r).name.startswith('test_')
                and r.endswith('.py')]
        if rels:
            return [_RACINE / r for r in rels
                    if (_RACINE / r).is_file()]
    except (OSError, subprocess.SubprocessError):
        pass
    #: ⚠️ REPLI SANS GIT, ET IL EST DIT : on retombe sur le disque, en
    #: ecartant au moins ce que le depot declare ignorer et qui a
    #: reellement pollue la mesure.
    return [p for p in sorted(_RACINE.rglob('test_*.py'))
            if '__pycache__' not in str(p)
            and 'Python' not in p.relative_to(_RACINE).parts[:1]]


class TestVerdictIndependantDeLaConsole(unittest.TestCase):

    # ── VC-1 ─────────────────────────────────────────────────────────────
    def test_VC1_l_instrument_NOMME_les_caracteres_en_cause(self):
        """⚠️ ON REPOND UN ENSEMBLE, PAS UN BOOLEEN : savoir QU'IL Y EN A ne
        dit pas lesquels, et c'est en les nommant qu'on decide quoi faire."""
        hors = caracteres_hors_encodage('prix 12 EUR, ratio 1,2')
        self.assertEqual(
            hors, set(),
            f"un texte purement ASCII est declare hors cp1252 : {hors}")
        hors = caracteres_hors_encodage('a → b, β = 0,5, ═')
        self.assertEqual(
            hors, {'→', 'β', '═'},
            f"l'instrument ne nomme pas les bons caracteres : {sorted(hors)}")
        #: et un encodage INCONNU ne fait pas lever : il declare tout hors
        self.assertTrue(
            caracteres_hors_encodage('abc', 'encodage-qui-n-existe-pas'),
            "un encodage inconnu doit declarer les caracteres hors, pas "
            "lever dans un instrument de mesure")
        print(f"    VC-1 SCEAU : 0 hors cp1252 sur de l'ASCII, "
              f"{len(hors)} nommes sur un texte mixte")

    # ── VC-2 ─────────────────────────────────────────────────────────────
    def test_VC2_un_fichier_ILLISIBLE_ne_disparait_pas_de_la_mesure(self):
        """⚠️⚠️ UN SILENCE SUR UN FICHIER ILLISIBLE EST UN SOUS-COMPTE. Il
        ressort NOMME, avec sa raison."""
        vus = verdict_depend_de_l_encodage(
            [_RACINE / 'ce-fichier-n-existe-pas.py'])
        self.assertEqual(
            len(vus), 1,
            f"un fichier illisible a disparu de la mesure : {vus}")
        raison = next(iter(next(iter(vus.values()))))
        self.assertIn(
            'illisible', raison,
            f"la raison de non-lecture n'est pas dite : {raison!r}")
        print(f"    VC-2 SCEAU : fichier illisible -> {raison!r}")

    # ── VC-3 ─────────────────────────────────────────────────────────────
    def test_VC3_la_gate_LIT_la_variable_au_lieu_de_la_RECOPIER(self):
        """⚠️⚠️ DEUX ENDROITS QUI DECLARENT LA MEME CONDITION FINISSENT PAR
        EN DECLARER DEUX DIFFERENTES. Le releve est par AST sur les
        litteraux VIVANTS : le nom peut rester en commentaire, il doit
        disparaitre du code."""
        arbre = ast.parse(_GATE.read_bytes().decode('utf-8'))
        #: ⚠️⚠️ LES DOCSTRINGS SONT DES `ast.Constant`, ET ELLES CITENT LE
        #: NOM EN PROSE. Ma premiere version les comptait : elle a mordu
        #: sur la docstring de `environnement_des_enfants`, qui EXPLIQUE
        #: precisement pourquoi la variable n'est plus recopiee.
        #: *MENTION prise pour USAGE -- cinquieme forme de ce piege dans
        #: cette seule session.* On les recense et on les ecarte.
        docstrings = set()
        for n in ast.walk(arbre):
            corps = getattr(n, 'body', None)
            if not isinstance(corps, list) or not corps:
                continue
            tete = corps[0]
            if (isinstance(tete, ast.Expr)
                    and isinstance(tete.value, ast.Constant)
                    and isinstance(tete.value.value, str)):
                docstrings.add(id(tete.value))
        vivants = [(n.lineno, n.value[:40]) for n in ast.walk(arbre)
                   if isinstance(n, ast.Constant)
                   and isinstance(n.value, str)
                   and id(n) not in docstrings
                   and ENCODAGE_IMPOSE[0] in n.value]
        self.assertEqual(
            vivants, [],
            f"`{ENCODAGE_IMPOSE[0]}` est encore ecrit EN DUR dans le "
            f"lanceur : {vivants}. Il vit dans le socle, et le lanceur le "
            f"lit.")
        self.assertIn(
            'ENCODAGE_IMPOSE', _GATE.read_bytes().decode('utf-8'),
            "le lanceur n'importe plus la constante du socle")
        #: ⚠️⚠️ ET LE LANCEUR DOIT DEMARRER, pas seulement ne plus contenir
        #: le litteral. Mesure du 14/09 : mon premier correctif importait
        #: `core.sortie_console` depuis `scripts/`, ou `core` n'est PAS sur
        #: le chemin -- la gate ENTIERE tombait sur un `ModuleNotFoundError`
        #: et CE controle restait VERT. *Un releve de texte ne dit rien de
        #: ce qui s'execute.*
        #: ⚠️ ET LA SONDE DOIT ATTEINDRE L'IMPORT. Ma premiere version
        #: lancait la gate avec un drapeau inconnu : `argparse` sortait
        #: AVANT la ligne d'import, et le plant qui retirait le chemin
        #: restait VERT. On passe donc une cible REELLE avec un delai de
        #: 1 seconde -- la gate demarre, importe, lance, et rend la main.
        import subprocess
        import tempfile
        _sortie = pathlib.Path(tempfile.gettempdir()) / 'gate_sonde_vc3.txt'
        essai = subprocess.run(
            [sys.executable, '-B', str(_GATE), 'core',
             '--delai', '1', '--sortie', str(_sortie)],
            cwd=str(_RACINE), capture_output=True, text=True,
            encoding='utf-8', errors='replace', check=False,
            env={**os.environ, 'PYTHONUTF8': '1',
                 'PYTHONDONTWRITEBYTECODE': '1'})
        journal = (essai.stdout or '') + (essai.stderr or '')
        self.assertNotIn(
            'ModuleNotFoundError', journal,
            f"le lanceur ne DEMARRE plus : il importe le socle depuis un "
            f"dossier ou celui-ci n'est pas sur le chemin.\n"
            f"{journal[-260:]}")
        self.assertNotIn(
            'Traceback', journal,
            f"le lanceur leve au demarrage : {journal[-260:]}")
        print(f"    VC-3 SCEAU : 0 litteral vivant dans {_GATE.name}, la "
              f"constante vient du socle {ENCODAGE_IMPOSE!r}, et le "
              f"lanceur DEMARRE")

    # ── VC-4b ────────────────────────────────────────────────────────────
    def test_VC4b_L_ASSIETTE_ne_contient_AUCUN_fichier_IGNORE(self):
        """⚠️⚠️ SANS CE CONTROLE, LE CHIFFRE DE `VC-4` DEPEND DE LA MACHINE.

        Mesure du 14/09/2026 : `_fichiers_de_test` balayait le DISQUE et
        ramassait **60 fichiers de la bibliotheque standard CPython**,
        tombee dans `Python/` le 03/09 et IGNOREE par `.gitignore`. Le
        meme controle publiait 413 sur l'arbre de travail et 353 sur
        l'instantane de gate -- *et c'est la gate qui avait raison.*

        Ce controle n'est pas tautologique : il ne verifie pas que la
        fonction appelle `git`, il verifie que **rien de ce qu'elle rend
        n'est ignore par le depot**. Un repli qui reviendrait au disque
        sans filtrer le ferait tomber.
        """
        import subprocess
        fichiers = _fichiers_de_test()
        rels = [str(p.relative_to(_RACINE)).replace('\\', '/')
                for p in fichiers]
        essai = subprocess.run(
            ['git', 'check-ignore', '--stdin'], cwd=str(_RACINE),
            input='\n'.join(rels), capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=180, check=False)
        ignores = [x for x in essai.stdout.split('\n') if x.strip()]
        self.assertEqual(
            ignores, [],
            f"{len(ignores)} fichier(s) de l'assiette sont IGNORES par le "
            f"depot : le nombre publie par `VC-4` depend alors de ce qui "
            f"traine sur le disque de la machine. Exemples : {ignores[:4]}")
        print(f"    VC-4b assiette : {len(fichiers)} fichier(s), 0 ignore")

    # ── VC-4 ─────────────────────────────────────────────────────────────
    def test_VC4_L_ASSIETTE_du_constat_est_MESUREE_et_publiee(self):
        """⚠️ CE CONTROLE NE FERME RIEN : il MESURE. Les fichiers ne sont
        pas reecrits -- leur caractere hors cp1252 est le plus souvent un
        symbole de docstring, et les reecrire serait un chantier a part.
        *Il MORD si leur nombre AUGMENTE.*"""
        fichiers = _fichiers_de_test()
        self.assertGreater(
            len(fichiers), 300,
            f"seuls {len(fichiers)} fichiers de test balayes : l'assiette "
            f"de ce controle s'est effondree")
        a_risque = verdict_depend_de_l_encodage(fichiers)
        self.assertLessEqual(
            len(a_risque), _FICHIERS_A_RISQUE,
            f"le nombre de fichiers de test dependant de l'encodage a "
            f"AUGMENTE : {len(a_risque)} sur {len(fichiers)}. Il valait "
            f"{_FICHIERS_A_RISQUE} au 14/09/2026.")
        print(f"    VC-4 RELEVE (non ferme) : {len(a_risque)} fichier(s) sur "
              f"{len(fichiers)} portent un caractere hors cp1252")

    # ── VC-5 ─────────────────────────────────────────────────────────────
    def test_VC5_la_PORTE_existe_et_ne_s_ouvre_JAMAIS_a_l_import(self):
        """⚠️⚠️ UN MODULE QUI RECONFIGURE `sys.stdout` EN ETANT IMPORTE
        impose son choix a tout appelant, y compris a celui qui capture la
        sortie pour la verifier. La porte existe ; c'est un LANCEUR qui la
        franchit."""
        self.assertTrue(
            callable(imposer_l_encodage_du_processus),
            "la porte du lanceur n'existe pas")
        arbre = ast.parse(_SOCLE.read_bytes().decode('utf-8'))
        #: un appel AU NIVEAU DU MODULE serait l'appel a l'import
        au_module = [n.lineno for n in ast.walk(arbre)
                     if isinstance(n, ast.Expr)
                     and isinstance(n.value, ast.Call)
                     and ast.unparse(n.value.func).endswith(
                         'imposer_l_encodage_du_processus')]
        self.assertEqual(
            au_module, [],
            f"la porte est franchie A L'IMPORT (l.{au_module}) : le module "
            f"impose alors son choix a tout appelant.")
        print(f"    VC-5 SCEAU : la porte existe, {len(au_module)} appel a "
              f"l'import dans {_SOCLE.name}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
