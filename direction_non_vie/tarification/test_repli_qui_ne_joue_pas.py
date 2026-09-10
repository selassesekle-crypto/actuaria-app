"""
==============================================================================
  UN REPLI QUI NE JOUE PAS -- `.get(cle, defaut)` FACE A UN `None` EXPLICITE
==============================================================================

⚠️⚠️ CE QUE CE LOT FERME, ET IL COUTAIT LE DOCUMENT ENTIER. `dict.get(cle,
defaut)` ne substitue son defaut QUE si la cle est ABSENTE. Une cle PRESENTE
valant `None` traverse le defaut -- et la valeur `None` continue son chemin
jusqu'au premier appel de methode de `str`, ou elle leve.

  Mesure du 10/09/2026, relevee PAR AST sur le perimetre :
    · CINQ agents posent `'branche': None` dans leur `_erreur()` -- a2, a3,
      a4, a5 et a6, pas seulement a6 ;
    · VINGT ET UN sites lisent `'branche'` avec un `.get(cle, defaut)` ;
    · DEUX de ces lectures alimentent des `.replace()`, a neuf endroits, dans
      `rapport_modeles_tarif` -- donc `AttributeError`, donc **le rapport
      entier n'est pas produit**.

⚠️ LE REMEDE EST AUX DEUX BOUTS, et il faut les deux : a la SOURCE les cinq
`_erreur()` posent `'inconnue'` -- le repli que `run()` utilise deja --, et a
la LECTURE les vingt et un sites passent a `(... .get('branche') or <defaut>)`.
`or` traite `None` ET `''` ; `get` ne traite ni l'un ni l'autre.

⚠️⚠️ POURQUOI LES DEUX. Fermer la seule source laisserait tout futur
producteur rouvrir le trou ; fermer la seule lecture laisserait `None`
voyager dans le contrat de sortie, ou d'autres lecteurs le trouveront.
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

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from direction_non_vie.tarification.a6_comparaison.agent import (
    AgentA6Comparaison,
)
from direction_non_vie.tarification.services import (
    rapport_modeles_tarif as RM,
)

#: ⚠️ L'ASSIETTE DU CONTROLE -- le perimetre du lot, et lui seul.
_PERIMETRE = ('direction_non_vie/tarification/', 'core/')
#: La cle mesuree comme posable a `None` par un producteur du perimetre.
_CLE = 'branche'


def _fichiers_du_perimetre() -> list[pathlib.Path]:
    """Les .py SUIVIS du perimetre -- avec un repli si git est absent."""
    racine = pathlib.Path(_RACINE)
    try:
        sortie = subprocess.run(
            ['git', 'ls-files'], cwd=_RACINE, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=120, check=False).stdout
        rels = [f for f in sortie.split('\n')
                if f.endswith('.py')
                and any(f.startswith(p) for p in _PERIMETRE)]
        if rels:
            return [racine / r for r in rels if (racine / r).is_file()]
    except (OSError, subprocess.SubprocessError):
        pass
    fichiers = []
    for p in _PERIMETRE:
        fichiers += [f for f in (racine / p).rglob('*.py')
                     if '.git' not in f.parts]
    return fichiers


class TestAucunRepliQuiNeJouePas(unittest.TestCase):

    def test_RP1_LE_SCEAU_aucun_get_avec_defaut_sur_une_cle_posable_a_None(
            self):
        """⚠️⚠️ LE CONTROLE CENTRAL, ET IL PORTE SUR LE PERIMETRE ENTIER. Un
        plant qui remettrait `.get('branche', 'non_vie')` a l'UN des vingt et
        un sites doit faire rougir ceci. *Verifier le seul site qui levait
        laisserait vingt autres publier `None` la ou ils croient publier un
        repli lisible.*"""
        fautifs = []
        for p in _fichiers_du_perimetre():
            try:
                arbre = ast.parse(p.read_text(encoding='utf-8'))
            except (SyntaxError, OSError):
                continue
            for n in ast.walk(arbre):
                if (isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and n.func.attr == 'get'
                        and len(n.args) == 2
                        and isinstance(n.args[0], ast.Constant)
                        and n.args[0].value == _CLE):
                    fautifs.append(
                        f"{p.relative_to(_RACINE)}:{n.lineno}")
        self.assertEqual(
            fautifs, [],
            f"{len(fautifs)} site(s) lisent '{_CLE}' avec un defaut que "
            f"`get` ne substituera PAS a un `None` explicite : {fautifs[:8]}")
        print(f"    RP-1 SCEAU : 0 site sur "
              f"{len(_fichiers_du_perimetre())} fichiers du perimetre")

    def test_RP2_aucun_producteur_ne_pose_plus_la_cle_a_None(self):
        """⚠️⚠️ LA SOURCE, ET LES CINQ AGENTS -- pas seulement A6. Une seule
        source rouverte suffit a faire voyager `None` dans tout le contrat de
        sortie."""
        poseurs = []
        for p in _fichiers_du_perimetre():
            try:
                arbre = ast.parse(p.read_text(encoding='utf-8'))
            except (SyntaxError, OSError):
                continue
            for fn in ast.walk(arbre):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for d in ast.walk(fn):
                    if not isinstance(d, ast.Dict):
                        continue
                    for k, v in zip(d.keys, d.values):
                        if (isinstance(k, ast.Constant) and k.value == _CLE
                                and isinstance(v, ast.Constant)
                                and v.value is None):
                            poseurs.append(
                                f"{p.relative_to(_RACINE)}:{d.lineno}"
                                f" dans {fn.name}()")
        self.assertEqual(
            poseurs, [],
            f"{len(poseurs)} producteur(s) posent encore '{_CLE}' a `None` : "
            f"{poseurs}")
        print("    RP-2 aucune source ne pose plus la cle a None")

    def test_RP3_LE_SCEAU_le_rapport_SORT_sur_un_resultat_d_ECHEC(self):
        """⚠️⚠️ LA PROPRIETE QUI COMPTE, MESUREE PAR EXECUTION. Lire le code
        dirait seulement qu'un `or` y est ecrit. Ici on fabrique le vrai
        resultat d'echec d'A6 et on demande les DEUX documents. *Un rapport
        perdu est pire que le defaut qu'il devait signaler : l'actuaire n'a
        alors AUCUNE trace de l'echec.*"""
        echec = AgentA6Comparaison(audit_path='/tmp', verbose=False)._erreur(
            "panne simulee par le controle RP-3", 'RP3')
        self.assertFalse(echec['success'])
        self.assertIsNotNone(
            echec.get(_CLE),
            "le resultat d'echec pose encore `None` : la lecture aura beau "
            "se defendre, la valeur voyagera dans le contrat de sortie")

        html = RM.export_html(result_a6=echec)
        self.assertIsInstance(html, str)
        self.assertGreater(
            len(html), 1000,
            "le rapport HTML n'est pas produit sur un resultat d'echec")

        word = RM.export_word(result_a6=echec)
        self.assertIsNotNone(word)
        self.assertGreater(
            len(word), 1000,
            "le rapport Word n'est pas produit sur un resultat d'echec")
        print(f"    RP-3 SCEAU : sur un ECHEC, HTML {len(html)} car. et "
              f"Word {len(word)} octets -- les deux SORTENT")

    def test_RP4_CONTRE_EPREUVE_la_VRAIE_branche_atteint_le_document(self):
        """⚠️ Un `or` avale aussi les valeurs FAUSSES. Une branche reelle est
        une chaine non vide : elle doit traverser jusqu'au document. Sans ce
        controle, un correctif qui rendrait TOUJOURS le repli passerait RP-1
        a RP-3.

        ⚠️⚠️ CE CONTROLE A ETE REECRIT LE 10/09/2026, ET C'EST UNE LECON. Sa
        premiere version comparait `d.get(k) or x` a la valeur attendue : elle
        mesurait le comportement de PYTHON, qui ne peut pas regresser. *Son
        assiette vis-a-vis du depot etait VIDE* -- aucun plant du dossier
        n'aurait pu la faire rougir. Il porte desormais sur le DOCUMENT
        REELLEMENT PRODUIT."""
        # ⚠️⚠️ ON ANCRE SUR LE CHAMP NOMME, PAS SUR LE DOCUMENT ENTIER.
        # Premiere version : `assertIn('auto', html)` -- satisfaite par le CSS
        # (`height:auto`), donc VERTE sans rien surveiller. Et le document
        # publie la branche CAPITALISEE (`Mrh`), donc la comparaison brute
        # echouait sur une valeur pourtant juste. *Trop laxiste d'un cote,
        # trop stricte de l'autre : le meme defaut d'assiette, deux fois.*
        champ = re.compile(r'>Branche</span><span class="val">([^<]*)<')

        for reelle in ('auto', 'mrh', 'rc_generale'):
            with self.subTest(branche=reelle):
                vrai = {'success': True, _CLE: reelle, 'statut_rag': 'VERT'}
                trouve = champ.search(RM.export_html(result_a6=vrai))
                self.assertIsNotNone(
                    trouve, "le champ « Branche » a disparu du document : "
                            "ce controle n'atteste plus rien")
                # ⚠️ LE DOCUMENT MET EN FORME : `_` devient une espace et le
                # tout est capitalise -- c'est precisement le `.replace()` qui
                # LEVAIT sur `None`. On compare donc la valeur MISE EN FORME,
                # pas la brute : `rc_generale` -> « Rc generale ».
                self.assertEqual(
                    trouve.group(1).lower(), reelle.replace('_', ' ').lower(),
                    f"le document publie '{trouve.group(1)}' la ou la branche "
                    f"reelle est '{reelle}' : le repli l'a mangee en chemin")
        # ⚠️ ET LE MIROIR, SUR LE MEME CHAMP : une branche creuse ne doit PAS
        # publier `None` -- c'est exactement ce que le defaut produisait.
        for creuse in (None, ''):
            with self.subTest(branche=creuse):
                creux = {'success': True, _CLE: creuse, 'statut_rag': 'VERT'}
                trouve = champ.search(RM.export_html(result_a6=creux))
                self.assertIsNotNone(trouve)
                self.assertNotIn(
                    'none', trouve.group(1).lower(),
                    "le document publie `None` comme nom de branche : le "
                    "repli n'a pas joue")
                self.assertTrue(
                    trouve.group(1).strip(),
                    "le champ « Branche » est VIDE : un repli qui ne remplace "
                    "rien ne vaut pas mieux que `None`")
        print("    RP-4 contre-epreuve : la vraie branche atteint le "
              "document, `None` n'y est jamais publie")

    def test_RP5_le_repli_pose_a_la_source_est_celui_que_run_utilise(self):
        """⚠️ Deux replis differents pour le meme fait finissent par en dire
        deux choses. `run()` lit `result_a2.get('branche') or 'inconnue'` ;
        `_erreur()` doit poser le MEME mot."""
        echec = AgentA6Comparaison(audit_path='/tmp', verbose=False)._erreur(
            "panne simulee par le controle RP-5", 'RP5')
        a6 = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
              / 'a6_comparaison' / 'agent.py')
        arbre = ast.parse(a6.read_text(encoding='utf-8'))
        replis = set()
        for n in ast.walk(arbre):
            if (isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or)
                    and len(n.values) == 2
                    and isinstance(n.values[0], ast.Call)
                    and isinstance(n.values[0].func, ast.Attribute)
                    and n.values[0].func.attr == 'get'
                    and n.values[0].args
                    and isinstance(n.values[0].args[0], ast.Constant)
                    and n.values[0].args[0].value == _CLE
                    and isinstance(n.values[1], ast.Constant)):
                replis.add(n.values[1].value)
        self.assertIn(
            echec[_CLE], replis,
            f"`_erreur()` pose '{echec[_CLE]}' alors que la lecture d'A6 "
            f"replie sur {sorted(replis)} : deux mots pour le meme fait")
        print(f"    RP-5 la source pose '{echec[_CLE]}', le meme mot que la "
              f"lecture")


if __name__ == '__main__':
    unittest.main(verbosity=2)
