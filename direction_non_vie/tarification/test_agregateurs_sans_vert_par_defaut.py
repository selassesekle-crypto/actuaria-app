"""AUCUN AGREGATEUR DE STATUT NE CERTIFIE SUR UN JETON QU'IL NE CONNAIT PAS.

Les CINQ agregateurs de la zone ecrivaient la meme ligne :

    "ROUGE" if "ROUGE" in statuts else "AMBRE" if "AMBRE" in statuts
    else "VERT"

La branche TERMINALE est le cas le plus FAVORABLE. Tout jeton qui n'est ni
`ROUGE` ni `AMBRE` -- un quatrieme mot, une faute de frappe, une cle absente
devenue `None` -- y tombe et ressort **VERT**, c'est-a-dire
<< Modele valide, pret pour la production >> dans un document signe.

  *Une echelle dont le defaut est le cas favorable est un litteral neutre
  deguise en logique, et il se pose dans la direction rassurante -- celle qui
  ne se remarque pas.*

⚠️⚠️ TROUVE PAR L'AUDITEUR INDEPENDANT LE 07/09/2026, EN VERIFIANT CE QUE
COUTAIT UN QUATRIEME MOT. Il en avait vu deux ; le releve AST en a trouve
CINQ. Sans cette reparation, `H1 = NON CONCLUANT` aurait produit
<< Modele valide >> sur 88 % des dossiers.

⚠️ ET DEUX SITES QUI RESSEMBLENT AU DEFAUT N'EN SONT PAS : `a1` et `a2`
terminent aussi par `return 'VERT'`, mais ce sont des CASCADES DE CONDITIONS,
pas des agregateurs de jetons -- leur VERT final signifie << aucune condition
n'a tire >>. *Un controle trop large accuse autant qu'un trop etroit dort.*

  AG-1  aucun agregateur de la zone ne retombe sur VERT ;
  AG-2  `statut_le_pire` ne certifie que sur des jetons connus VERT ;
  AG-3  un `None` dans la liste ne se laisse pas ecarter ;
  AG-4  second sens : des statuts tous VERTS donnent bien VERT ;
  AG-5  le consolide du rapport d'equipe suit la meme regle.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""

from __future__ import annotations

import ast
import os
import pathlib
import sys
import unittest

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

from core.conformite_reglementaire import (
    STATUT_NON_CONCLUANT,
    statut_le_pire,
)

_ZONES = ('core', 'direction_non_vie/tarification')


class TestAucunVertParDefaut(unittest.TestCase):

    def test_AG1_aucun_agregateur_ne_retombe_sur_VERT(self):
        """⚠️ PAR AST, et sur toute la zone. Le critere est la FORME du
        defaut : une expression qui teste l'appartenance a une liste de
        statuts et dont la branche terminale est VERT."""
        fautifs = []
        for zone in _ZONES:
            for chemin in sorted((pathlib.Path(_RACINE) / zone).rglob('*.py')):
                s = chemin.relative_to(_RACINE).as_posix()
                if ('.venv' in s or 'audit_2026_08' in s
                        or chemin.name.startswith('test_')):
                    continue
                source = chemin.read_text(encoding='utf-8', errors='replace')
                try:
                    arbre = ast.parse(source)
                except SyntaxError:                     # pragma: no cover
                    continue
                for n in ast.walk(arbre):
                    if not isinstance(n, ast.IfExp):
                        continue
                    seg = (ast.get_source_segment(source, n) or '')
                    plat = seg.replace('\n', ' ')
                    # un AGREGATEUR : il teste l'appartenance (`in`) a une
                    # collection de statuts, et il finit par VERT.
                    if ('ROUGE' in plat and 'AMBRE' in plat
                            and ' in ' in plat
                            and plat.rstrip().endswith(("'VERT'", '"VERT"'))):
                        fautifs.append(f'{s}:{n.lineno}')
        self.assertEqual(
            fautifs, [],
            f'{len(fautifs)} agregateur(s) certifient VERT sur un jeton '
            f'inconnu : {fautifs}')
        print('    AG-1 aucun agregateur ne retombe sur VERT')

    def test_AG2_statut_le_pire_ne_certifie_que_sur_du_connu(self):
        for jetons in (['VERT', STATUT_NON_CONCLUANT],
                       ['VERT', 'TYPO'],
                       ['VERT', 'NON DETERMINE'],
                       [STATUT_NON_CONCLUANT]):
            with self.subTest(jetons=jetons):
                self.assertNotEqual(
                    statut_le_pire(jetons), 'VERT',
                    f'{jetons} ressort VERT : un jeton inconnu certifie')
        self.assertEqual(statut_le_pire(['VERT', 'ROUGE']), 'ROUGE')
        self.assertEqual(statut_le_pire(['VERT', 'AMBRE']), 'AMBRE')
        print('    AG-2 aucun jeton inconnu ne certifie')

    def test_AG3_un_None_ne_se_laisse_pas_ecarter(self):
        """⚠️⚠️ LE TROU DE MA PREMIERE VERSION. Elle filtrait `if s`, donc
        `['VERT', None]` rendait **VERT** : un statut manquant devenait une
        certification -- le defaut que cette fonction existe pour fermer,
        survivant dans le correctif."""
        self.assertNotEqual(statut_le_pire(['VERT', None]), 'VERT')
        self.assertNotEqual(statut_le_pire(['VERT', '']), 'VERT')
        self.assertNotEqual(statut_le_pire([None]), 'VERT')
        # ⚠️ Et une liste VIDE ne vaut pas VERT non plus : rien n'a ete agrege.
        self.assertEqual(statut_le_pire([]), STATUT_NON_CONCLUANT)
        print('    AG-3 un statut manquant ne certifie jamais')

    def test_AG4_second_sens_tous_verts_donnent_VERT(self):
        """⚠️ Sans ce sens, une fonction qui ne rendrait JAMAIS vert passerait
        les trois precedents -- et le statut ne servirait plus a rien."""
        self.assertEqual(statut_le_pire(['VERT']), 'VERT')
        self.assertEqual(statut_le_pire(['VERT', 'VERT', 'VERT']), 'VERT')
        self.assertEqual(statut_le_pire(['vert', 'VERT']), 'VERT')
        print('    AG-4 des statuts tous verts donnent bien VERT')

    def test_AG5_le_consolide_du_rapport_d_equipe_suit_la_meme_regle(self):
        """⚠️ Le cinquieme site n'est pas un ternaire mais une cascade : il
        faut le verifier par le COMPORTEMENT, pas par la forme."""
        from direction_non_vie.tarification.services.rapport_equipe_tarif import (
            STATUT_NON_FOURNI,
            _statut_global,
        )
        self.assertEqual(_statut_global(['VERT', 'VERT']), 'VERT')
        self.assertNotEqual(
            _statut_global(['VERT', STATUT_NON_CONCLUANT]), 'VERT',
            'le consolide certifie sur un jeton inconnu')
        self.assertNotEqual(_statut_global(['VERT', 'TYPO']), 'VERT')
        self.assertEqual(_statut_global(['VERT', 'ROUGE']), 'ROUGE')
        # ⚠️ L'absence LEGITIME reste filtree au site : un agent facultatif
        # qu'on n'a pas lance n'est pas une anomalie.
        self.assertEqual(_statut_global(['VERT', STATUT_NON_FOURNI]), 'VERT')
        print('    AG-5 le consolide ne certifie pas sur un inconnu')


if __name__ == '__main__':
    unittest.main(verbosity=2)
