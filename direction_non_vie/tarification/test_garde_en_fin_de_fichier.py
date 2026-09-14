r"""
==============================================================================
  AUCUN TEST N'EST INVISIBLE PAR LA PORTE QUE LE FICHIER INVITE A PRENDRE
==============================================================================

⚠️⚠️ `TEST-D1` -- QUATRE FICHIERS PORTAIENT UNE CLASSE DE TEST APRES
`if __name__ == '__main__': unittest.main()`. `unittest.main()`
s'execute puis appelle `sys.exit()` : **tout ce qui suit n'est JAMAIS
defini**.

La gate (`unittest discover`) IMPORTE le module et les voit ; la porte
DIRECTE -- celle qu'on emprunte pour verifier un fichier qu'on est en
train de modifier, et que le pied de page invite explicitement -- non.

Mesure du 14/09/2026, `PYTHONPATH` pose sur la racine :

    core/test_proprete_outil.py       directe  5 | discover 10
    test_liste_disqualifiante.py      directe 11 | discover 21
    -> QUINZE tests sur trente-et-un INVISIBLES dans le perimetre.

Apres correctif : 10 et 21 par les DEUX portes.

⚠️ LE `PYTHONPATH` COMPTE, et ma premiere mesure l'avait oublie : sans
lui, trois des quatre fichiers ne DEMARRENT pas du tout
(`ModuleNotFoundError`), et le compte << directe >> vaut 0 pour une
raison qui n'a rien a voir avec ce constat. *Une sonde qui ne peut pas
atteindre le site qu'elle mesure ne mesure rien.*

⚠️ DEUX FICHIERS SONT HORS PERIMETRE, et l'auditeur les marque comme
tels : `normes/ifrs17/mesure/test_lic.py` (directe 17 | discover 24) et
`normes/ifrs17/socle/test_registre.py` (directe 20 | discover 25).
`GD-3` les MESURE et publie leur etat sans les fermer -- et il MORD si
leur nombre augmente.

⚠️ LE DEPOT A DEJA PAYE CETTE CLASSE DE DEFAUT : 163 tests invisibles,
03/09/2026.
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import re
import subprocess
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

#: Le perimetre de ce chantier. `normes/` en est dehors, l'auditeur le dit.
_PERIMETRE = ('core', 'direction_non_vie')
#: ⚠️ NOMMES, PAS IGNORES : leur etat est mesure par `GD-3`.
_HORS_PERIMETRE = ('normes/ifrs17/mesure/test_lic.py',
                   'normes/ifrs17/socle/test_registre.py')
_REPARES = ('core/test_proprete_outil.py',
            'direction_non_vie/tarification/test_liste_disqualifiante.py')
_ENV = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
            PYTHONIOENCODING='utf-8', PYTHONPATH=str(_RACINE))


def _fichiers_de_test():
    for chemin in sorted(_RACINE.rglob('test_*.py')):
        plat = str(chemin).replace('\\', '/')
        if '__pycache__' in plat:
            continue
        yield chemin, plat[len(str(_RACINE).replace('\\', '/')) + 1:]


def _classes_apres_la_garde(chemin) -> list:
    """Les classes de test definies APRES le dernier `unittest.main()`."""
    try:
        arbre = ast.parse(chemin.read_bytes().decode('utf-8', 'replace'))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []
    gardes = [n.lineno for n in ast.walk(arbre)
              if isinstance(n, ast.Call)
              and ast.unparse(n.func).endswith('unittest.main')]
    if not gardes:
        return []
    return [n.name for n in arbre.body
            if isinstance(n, ast.ClassDef) and n.lineno > max(gardes)]


def _compte(commande) -> int | None:
    #: ⚠️ `check=False` EXPLICITE : un fichier de test qui ECHOUE sort en
    #: code non nul, et c'est un cas NORMAL ici -- on compte des tests, on
    #: ne juge pas leur verdict. Lever sur le code de sortie ferait rougir
    #: ce controle pour une raison etrangere a ce qu'il mesure.
    p = subprocess.run(commande, cwd=str(_RACINE), capture_output=True,
                       text=True, encoding='utf-8', errors='replace',
                       env=_ENV, check=False)
    trouves = list(re.finditer(r'^Ran (\d+) tests? in ',
                               p.stdout + '\n' + p.stderr, re.MULTILINE))
    return int(trouves[-1].group(1)) if trouves else None


class TestGardeEnFinDeFichier(unittest.TestCase):

    # ── GD-1 ─────────────────────────────────────────────────────────────
    def test_GD1_AUCUN_fichier_du_perimetre_ne_cache_une_classe(self):
        """⚠️ LE RELEVE PORTE SUR TOUT LE PERIMETRE, pas sur deux noms : un
        troisieme fichier ecrit demain avec la meme faute doit mordre."""
        fautifs, balayes = {}, 0
        for chemin, rel in _fichiers_de_test():
            if not rel.startswith(_PERIMETRE):
                continue
            balayes += 1
            apres = _classes_apres_la_garde(chemin)
            if apres:
                fautifs[rel] = apres
        self.assertGreater(
            balayes, 100,
            f"seuls {balayes} fichiers balayes : l'assiette de ce controle "
            f"s'est effondree, il ne prouve plus rien")
        self.assertEqual(
            fautifs, {},
            f"{len(fautifs)} fichier(s) definissent une classe de test APRES "
            f"`unittest.main()` : {fautifs}. `sys.exit()` est appele avant, "
            f"donc ces classes n'existent JAMAIS par la porte directe.")
        print(f"    GD-1 SCEAU : {balayes} fichiers du perimetre balayes, "
              f"0 classe apres la garde")

    # ── GD-2 ─────────────────────────────────────────────────────────────
    def test_GD2_les_DEUX_portes_rendent_le_MEME_compte(self):
        """⚠️⚠️ LA PREUVE EST L'EXECUTION, pas la position de la garde. Un
        `unittest.main()` bien place mais un `sys.exit()` ailleurs ferait
        le meme degat, et ce controle le verrait."""
        vus = {}
        for rel in _REPARES:
            chemin = _RACINE / rel
            self.assertTrue(chemin.exists(), f"{rel} a disparu")
            directe = _compte([sys.executable, '-B', str(chemin)])
            dossier = str(pathlib.Path(rel).parent)
            discover = _compte([sys.executable, '-B', '-m', 'unittest',
                                'discover', '-s', dossier, '-t', '.',
                                '-p', pathlib.Path(rel).name])
            vus[rel] = (directe, discover)
        self.assertEqual(
            [x for x in vus.values() if None in x], [],
            f"une porte n'a rendu AUCUN `Ran N tests` : {vus}. Elle n'a pas "
            f"demarre, et son compte ne mesure pas ce constat.")
        ecarts = {k: v for k, v in vus.items() if v[0] != v[1]}
        self.assertEqual(
            ecarts, {},
            f"les deux portes ne rendent pas le meme compte : {ecarts}. "
            f"(directe, discover) -- la difference est le nombre de tests "
            f"INVISIBLES a qui verifie son fichier a la main.")
        print(f"    GD-2 SCEAU : {vus} -- les deux portes s'accordent")

    # ── GD-3 ─────────────────────────────────────────────────────────────
    def test_GD3_LES_HORS_PERIMETRE_sont_mesures_et_NOMMES(self):
        """⚠️ CE CONTROLE NE FERME RIEN : il MESURE et PUBLIE. L'auditeur
        marque ces deux fichiers hors perimetre ; on ne les corrige pas, et
        on ne fait pas semblant qu'ils n'existent pas. *Il MORD si leur
        nombre augmente.*"""
        ouverts = {}
        for chemin, rel in _fichiers_de_test():
            if rel.startswith(_PERIMETRE):
                continue
            apres = _classes_apres_la_garde(chemin)
            if apres:
                ouverts[rel] = apres
        self.assertLessEqual(
            len(ouverts), len(_HORS_PERIMETRE),
            f"le nombre de fichiers HORS PERIMETRE portant ce defaut a "
            f"AUGMENTE : {sorted(ouverts)}. Il valait "
            f"{len(_HORS_PERIMETRE)} au 14/09/2026.")
        print(f"    GD-3 RELEVE (non ferme) : {len(ouverts)} fichier(s) hors "
              f"perimetre -> {sorted(ouverts)}")

    # ── GD-4 ─────────────────────────────────────────────────────────────
    def test_GD4_la_MESURE_est_inscrite_a_cote_de_la_garde(self):
        """⚠️⚠️ SANS LA MESURE, UN FUTUR LOT REDEPLACE LA GARDE EN CROYANT
        RANGER. C'est exactement ce qui s'est produit ici, et c'est pour
        cela que le correctif recu demande d'inscrire les deux comptes."""
        manquants = []
        for rel in _REPARES:
            texte = (_RACINE / rel).read_bytes().decode('utf-8')
            queue = texte[texte.rfind('if __name__') - 1400:]
            if 'discover' not in queue or 'Ran' not in queue:
                manquants.append(rel)
        self.assertEqual(
            manquants, [],
            f"{manquants} ne portent plus la mesure a cote de leur garde : "
            f"le prochain lot la redeplacera sans savoir ce qu'elle coute.")
        print(f"    GD-4 SCEAU : les {len(_REPARES)} fichiers repares "
              f"portent leur mesure a cote de la garde")


if __name__ == '__main__':
    unittest.main(verbosity=2)
