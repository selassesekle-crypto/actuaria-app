# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — LE SCR PUBLIE EST MONO-LoB, ET LES TROIS SURFACES LE DISENT
=============================================================================

 Relevé du 11/09/2026 : le commentaire signé déclarait que le SCR porte sur
 une seule ligne d'activité, le classeur aussi — le HTML et le Word, non. Le
 document qu'on ouvre en premier était le seul à taire ce que son chiffre est.

 ⚠️ CE N'EST PAS UN DÉFAUT DE CALCUL. L'agrégation multi-LoB est opérée en
 aval : c'est un choix de périmètre assumé. Mais un périmètre qui ne voyage
 pas avec son chiffre n'est pas opposable.

 ⚠️⚠️ ON MESURE LES DOCUMENTS PRODUITS, pas la présence d'une constante dans
 le code. Une constante importée et jamais rendue laisserait les trois
 surfaces muettes.
=============================================================================
"""
import io
import logging
import re
import unittest
import warnings
import zipfile

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement,
)
from direction_non_vie.provisionnement.a7_provisionnement.n4_best_estimate import (
    PORTEE_SCR_MONO_LOB,
)

#: ⚠️⚠️ ON NE COUPE PAS LES JOURNAUX A L IMPORT. Le correctif recu posait
#: `logging.disable(logging.CRITICAL)` en tete de module ; le depot
#: l INTERDIT et `core/test_journaux_importables.py::F5_LeDepotEntier`
#: echoue dessus. La raison est ecrite dans `test_a7_ibrahim` l.347 : ce
#: motif a deja MASQUE un `logger.error` reel et laisse une regression
#: survivre DEUX lots. La sourdine reste, BORNEE a la duree des tests.
_SOURDINE = None


def setUpModule():
    """⚠️ LA SOURDINE EST BORNEE, ET POSEE AU NIVEAU DU MODULE.

    Le correctif recu coupait les journaux A L IMPORT.
    `core/test_journaux_importables.py::F5_LeDepotEntier` l interdit pour
    tout le depot, et la raison est ecrite dans `test_a7_ibrahim` l.347 : ce
    motif a deja MASQUE un `logger.error` reel et laisse une regression
    survivre DEUX lots (export Excel retombe a 0 octet).

    ⚠️ POURQUOI `setUpModule` ET NON `setUpClass`. Ce fichier definit deja un
    `setUpClass` ; la DERNIERE definition gagne, la mienne ne tournait donc
    jamais et `tearDownClass` recevait `None` — mesure : 3 erreurs sur 13
    tests. `setUpModule` n a pas ce probleme : unittest l appelle une fois,
    avant toute classe, et `tearDownModule` apres la derniere.
    """
    global _SOURDINE
    _SOURDINE = logging.root.manager.disable
    logging.disable(logging.CRITICAL)


def tearDownModule():
    logging.disable(_SOURDINE)


class T_La_Portee_Du_SCR_Voyage_Avec_Le_Chiffre(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        n = 7
        T = np.array([[1000.0 * (1.6 ** j) * (1 + 0.03 * i)
                       for j in range(n)] for i in range(n)])
        for i in range(n):
            for j in range(n):
                if i + j >= n:
                    T[i, j] = np.nan
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            cls.r = AgentA7Provisionnement(verbose=False).run(
                source=T, mode_declare='cumule', n_sim_bootstrap=20, seed=42,
                generer_graphiques=False, generer_word=True,
                generer_html=True)

    def test_le_dossier_publie_bien_un_SCR(self):
        """⚠️ SANS CE FAIT, LE RESTE MESURE LE VIDE."""
        self.assertTrue(self.r.get('success'), self.r.get('erreur'))
        scr = ((self.r.get('n4') or {}).get('scr') or {}).get('scr_provisions')
        self.assertIsNotNone(scr, 'aucun SCR publié : ce contrôle est muet')
        print('    OK LOB-1 le dossier publie un SCR (%s)' % scr)

    def test_les_trois_surfaces_chiffrees_portent_la_portee(self):
        """⚠️ ON LIT LES PRODUITS. Le HTML, le Word et le classeur portent
        chacun un chiffre de SCR ; chacun doit porter ce qu'il est."""
        html = self.r.get('html') or ''
        xml = zipfile.ZipFile(io.BytesIO(self.r['word_bytes'])).read(
            'word/document.xml').decode('utf-8', 'ignore')
        mot = ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', xml))
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(self.r['excel_bytes']))
        xls = ' | '.join(str(c.value) for ws in wb
                         for row in ws.iter_rows() for c in row
                         if c.value is not None)
        muets = []
        for nom, txt in (('HTML', html), ('Word', mot)):
            if PORTEE_SCR_MONO_LOB not in txt:
                muets.append(nom)
        # ⚠️ LE CLASSEUR PORTAIT DEJA SA PROPRE FORMULATION, PLUS LONGUE ET
        # PLUS TECHNIQUE. On ne la remplace pas : on vérifie qu'il dit le
        # FAIT, pas qu'il récite la même phrase.
        if 'seule LoB' not in xls and 'mono-branche' not in xls:
            muets.append('Excel')
        self.assertEqual(
            muets, [],
            'ces surfaces publient un SCR sans dire de quel périmètre il '
            'est : %s' % muets)
        print('    OK LOB-2 HTML, Word et classeur portent la portée')

    def test_le_commentaire_signe_le_dit_aussi(self):
        """⚠️ LA QUATRIEME SURFACE, celle qui est SIGNEE."""
        com = self.r.get('commentaire') or ''
        self.assertIn('une seule LoB', com,
                      'le commentaire signé ne dit plus le périmètre du SCR')
        print('    OK LOB-3 le commentaire signé porte le périmètre')

    def test_la_phrase_vit_a_UN_seul_endroit(self):
        """⚠️⚠️ DEUX COPIES DIVERGENT AU PREMIER AJUSTEMENT — la leçon des
        deux tables de libellés, et celle de la mention de troncature."""
        import pathlib
        from direction_non_vie.provisionnement.a7_provisionnement import (
            n5_rapport as R,
        )
        src = pathlib.Path(R.__file__).read_text(encoding='utf-8')
        self.assertNotIn(PORTEE_SCR_MONO_LOB, src,
                         'la phrase est recopiée dans le renderer')
        self.assertIn('PORTEE_SCR_MONO_LOB', src,
                      'le renderer ne référence plus la source unique')
        print('    OK LOB-4 la phrase vit dans n4, aucune copie locale')


if __name__ == '__main__':
    unittest.main(verbosity=1)
