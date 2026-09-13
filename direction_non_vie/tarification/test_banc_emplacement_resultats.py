r"""
==============================================================================
  UN RESULTAT PASSE AU MAUVAIS EMPLACEMENT MESURE UN AUTRE DOCUMENT
==============================================================================

⚠️⚠️ `PL-1` -- LE BANC QUI MESURE LE PASSAGE DES LIBELLES BATISSAIT SES
DEUX DOCUMENTS SANS A6. `export_html(result_a3, result_a4, result_a6, *,
result_a5=None)` : un resultat A6 passe en PREMIER entre dans
`result_a3`, et le document se construit avec `result_a6=None`. Le banc
appelait `RM.export_html(res)` sur un resultat A6 -- CINQ sites, releves
par AST (l.440, 441, 556, 557, 605).

Mesure du 13/09/2026, sur le resultat MARQUE du banc lui-meme :

    comme le banc appelait  export_html(res)          2 / 24 marqueurs
    emplacement correct     export_html(result_a6=)   3 / 24 marqueurs
    comme le banc appelait  export_word(res)          2 / 24 marqueurs
    emplacement correct     export_word(result_a6=)   3 / 24 marqueurs

*Le banc SOUS-COMPTE, et il sous-compte VERS L'ALARME : tout libelle qui
depend d'A6 y apparait absent -- ce qui est vrai du document que le banc
produit, et FAUX du document produit en production.*

⚠️⚠️ LE PIEGE A PRIS DEUX INSTRUMENTS INDEPENDANTS, ET C'EST LA MEILLEURE
PREUVE QU'IL EST REEL. L'auditeur le declare de ses propres sondes S24,
S26 et S27 ; et en dressant l'inventaire de ses dix-huit constats, j'ai
montre que sa sonde `s24` concluait a tort que `CE-1` n'atteignait pas
deux surfaces -- pour cette raison exacte. *Aucun des deux n'avait lu la
signature avant de compter.*

⚠️ CE CONTROLE SURVEILLE LA CLASSE, PAS LES CINQ SITES. Le depot possede
deja `exiger_harnais_valide`, le garde-fou ecrit pour ce cas -- et
`main()` ne l'appliquait pas. Plutot que de le poser a un endroit, on
interdit le GESTE partout : aucun appel a ces deux fabriques ne peut
placer un resultat par position sans atteindre l'emplacement d'A6.
==============================================================================
"""
from __future__ import annotations

import ast
import inspect
import logging
import os
import pathlib
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from direction_non_vie.tarification.audit_2026_08.preuves import (
    passage_libelles as PL,
)
from direction_non_vie.tarification.services import rapport_modeles_tarif as RM

_ZONE = _RACINE / 'direction_non_vie'
#: Les deux fabriques dont la signature porte le piege.
_FABRIQUES = ('export_html', 'export_word')


def _rang_de_result_a6() -> int:
    """Le RANG de `result_a6` dans la signature -- mesure, jamais devine.

    ⚠️ Si quelqu'un inserait un parametre, ce rang changerait et le seuil
    de ce controle avec lui. *Un seuil recopie a la main serait faux au
    premier refactor.*"""
    noms = [p.name for p in
            inspect.signature(RM.export_html).parameters.values()
            if p.kind is p.POSITIONAL_OR_KEYWORD]
    return noms.index('result_a6') + 1


class TestUnResultatAuBonEmplacement(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_BL1_SCEAU_aucun_appel_ne_place_un_resultat_PAR_DEFAUT(self):
        """⚠️⚠️ LE SCEAU DE LA CLASSE, RELEVE PAR AST SUR TOUTE LA DIRECTION.
        Un appel qui donne moins d'arguments positionnels qu'il n'en faut
        pour atteindre `result_a6` ne peut PAS y placer quoi que ce soit :
        soit il nomme ses arguments, soit il les compte."""
        rang = _rang_de_result_a6()
        #: ⚠️⚠️ UNE SEULE EXEMPTION, ET ELLE EST MESUREE. Ce fichier-ci fait
        #: DELIBEREMENT le mauvais appel, dans `BL-2`, pour mesurer l'ecart
        #: qu'il produit : sans cette exemption le controle s'accuserait
        #: lui-meme -- le piege exact que `PLA-4` avait deja tendu.
        #: *On plante la violation HORS de l'assiette, et on VERIFIE que
        #: l'exemption porte sur UN fichier et qu'il contient bien le geste
        #: demontre -- sinon elle deviendrait un blanc-seing.*
        exempte = pathlib.Path(os.path.abspath(__file__))
        #: ⚠️⚠️ ET L'EXEMPTION SE VERIFIE PAR L'USAGE, PAS PAR LA MENTION.
        #: Ma premiere redaction cherchait la CHAINE `'RM.export_html(res)'`
        #: dans ce fichier -- qui la contient TROIS fois : dans la docstring,
        #: dans le litteral de l'assertion elle-meme, et dans le vrai appel.
        #: Le plant qui retirait le vrai appel restait donc VERT. *Une
        #: MENTION prise pour un USAGE : le controle attestait sur son
        #: propre texte.* On compte desormais les APPELS, par AST.
        arbre_exempte = ast.parse(exempte.read_bytes().decode('utf-8'))
        demonstration = [
            n for n in ast.walk(arbre_exempte)
            if isinstance(n, ast.Call)
            and ast.unparse(n.func).split('.')[-1] in _FABRIQUES
            and len(n.args) == 1 and not n.keywords]
        self.assertTrue(
            demonstration,
            "ce fichier n'APPELLE plus la fabrique au mauvais emplacement "
            "(0 appel a un seul argument positionnel) : son exemption n'a "
            "plus d'objet et doit etre retiree")
        fautifs = []
        exemptes = 0
        for p in sorted(_ZONE.rglob('*.py')):
            if '__pycache__' in str(p):
                continue
            if p.resolve() == exempte.resolve():
                exemptes += 1
                continue
            try:
                arbre = ast.parse(p.read_bytes().decode('utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for n in ast.walk(arbre):
                if not isinstance(n, ast.Call):
                    continue
                cible = ast.unparse(n.func)
                if cible.split('.')[-1] not in _FABRIQUES:
                    continue
                #: ⚠️ ON NE RETIENT QUE LES FABRIQUES DE CE MODULE : les
                #: services voisins ont leurs propres `export_*`, avec
                #: d'autres signatures. *Un controle trop large ACCUSE.*
                if not (cible.startswith(('RM.', 'rapport_modeles_tarif.'))
                        or cible in _FABRIQUES):
                    continue
                if cible in _FABRIQUES and 'rapport_modeles_tarif' not in \
                        ast.unparse(arbre)[:4000]:
                    continue
                nomme = any(k.arg for k in n.keywords)
                if n.args and len(n.args) < rang and not nomme:
                    fautifs.append(
                        f'{p.relative_to(_RACINE)}:{n.lineno} '
                        f'{cible}({len(n.args)} positionnel(s))')
        self.assertEqual(
            fautifs, [],
            f"ces appels donnent moins de {rang} arguments positionnels et "
            f"n'en nomment aucun : le resultat passe entre dans "
            f"`result_a3`, et le document se batit avec `result_a6=None`.\n"
            + '\n  '.join(fautifs))
        self.assertEqual(exemptes, 1,
                         f'{exemptes} fichier(s) exempte(s) au lieu d un '
                         f'seul : l assiette s est elargie en silence')
        print(f"    BL-1 SCEAU : 0 appel positionnel court "
              f"(`result_a6` au rang {rang}, 1 fichier exempte et verifie)")

    def test_BL2_SCEAU_le_banc_compte_ce_que_le_document_PORTE(self):
        """⚠️⚠️ LE SCEAU PAR EXECUTION, SUR LE RESULTAT MARQUE DU BANC. Le
        nombre de marqueurs au bon emplacement doit etre STRICTEMENT
        superieur a celui du mauvais -- sinon le banc mesurerait la meme
        chose des deux facons, et le constat n'aurait pas de sens."""
        res = PL.resultat_a6_marque()
        mauvais = PL.texte_livrable(RM.export_html(res))
        bon = PL.texte_livrable(RM.export_html(result_a6=res))
        n_mauvais = sum(1 for c in PL.CHAMPS if PL.M(c) in mauvais)
        n_bon = sum(1 for c in PL.CHAMPS if PL.M(c) in bon)
        self.assertGreater(
            n_bon, n_mauvais,
            f"le bon emplacement ne publie pas PLUS de marqueurs que le "
            f"mauvais ({n_bon} contre {n_mauvais}) : le banc mesurerait la "
            f"meme chose des deux facons")
        self.assertGreater(len(bon), len(mauvais),
                           'le document au bon emplacement n est pas plus '
                           'long : A6 n y apporte rien')
        print(f"    BL-2 SCEAU : {n_mauvais} / {len(PL.CHAMPS)} marqueurs au "
              f"mauvais emplacement, {n_bon} au bon")

    def test_BL3_SCEAU_le_banc_lui_meme_route_vers_result_a6(self):
        """⚠️⚠️ ET LE BANC, LUI, EST-IL CORRIGE ? Le sceau precedent mesure
        la FABRIQUE ; celui-ci relit les CINQ sites du banc. *Un controle
        qui prouve que le mecanisme existe ne prouve pas qu'il est
        employe.*"""
        rang = _rang_de_result_a6()
        chemin = (_RACINE / 'direction_non_vie' / 'tarification'
                  / 'audit_2026_08' / 'preuves' / 'passage_libelles.py')
        arbre = ast.parse(chemin.read_bytes().decode('utf-8'))
        vus = []
        for n in ast.walk(arbre):
            if (isinstance(n, ast.Call)
                    and ast.unparse(n.func).split('.')[-1] in _FABRIQUES):
                vus.append((n.lineno, len(n.args),
                            [k.arg for k in n.keywords]))
        self.assertTrue(vus, 'le banc n appelle plus AUCUNE fabrique : '
                             'l assiette de ce controle est vide')
        courts = [(l, a, k) for l, a, k in vus if a and a < rang and not
                  any(x for x in k)]
        self.assertEqual(
            courts, [],
            f"{len(courts)} site(s) du banc passent encore un resultat par "
            f"position sans atteindre `result_a6` : {courts}")
        print(f"    BL-3 SCEAU : {len(vus)} appel(s) du banc, 0 positionnel "
              f"court")

    def test_BL4_la_TABLE_d_emplacement_nomme_de_VRAIS_parametres(self):
        """⚠️ LE CORRECTIF POSE UNE TABLE `_EMPLACEMENT` ECRITE A LA MAIN.
        *Une table a la main atteste ce qu'on a pense a y mettre* : on
        verifie que chacune de ses valeurs est un parametre REEL de la
        fabrique -- un renommage la rendrait fausse en silence."""
        table = getattr(PL, '_EMPLACEMENT', None)
        self.assertIsNotNone(table, 'la table `_EMPLACEMENT` a disparu')
        parametres = set(inspect.signature(RM.export_html).parameters)
        inconnus = sorted(v for v in table.values() if v not in parametres)
        self.assertEqual(
            inconnus, [],
            f"la table nomme des parametres qui n'existent pas dans "
            f"`export_html` : {inconnus}. Parametres reels : "
            f"{sorted(parametres)}")
        print(f"    BL-4 : {len(table)} emplacement(s) declares, tous "
              f"parametres reels de la fabrique")

    def test_BL5_CONTRE_EPREUVE_un_appel_NOMME_reste_permis(self):
        """⚠️ LE SECOND SENS. Le controle interdit le positionnel COURT, pas
        l'appel nomme ni l'appel complet : un garde-fou qui refuserait tout
        ne surveillerait rien."""
        res = PL.resultat_a6_marque()
        for etiq, appel in (
                ('nomme        ', lambda: RM.export_html(result_a6=res)),
                ('trois positions', lambda: RM.export_html(None, None, res))):
            txt = PL.texte_livrable(appel())
            n = sum(1 for c in PL.CHAMPS if PL.M(c) in txt)
            self.assertGreaterEqual(
                n, 3, f'{etiq} : {n} marqueur(s), A6 n atteint pas le '
                      f'document')
        print('    BL-5 contre-epreuve : appel nomme et appel a trois '
              'positions atteignent tous deux `result_a6`')


if __name__ == '__main__':
    unittest.main(verbosity=2)
