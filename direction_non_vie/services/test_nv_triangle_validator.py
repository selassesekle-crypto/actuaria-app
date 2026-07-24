# =============================================================================
#  Tests — nv_triangle_validator.py
#
#  Couvre le correctif de lecture Excel : pd.read_excel(sheet_name=None) rend un
#  DICT de toutes les feuilles, pas un DataFrame. _lire_source passait
#  nom_onglet (défaut None) tel quel → TOUT fichier Excel, mono comme
#  multi-onglets, par chemin comme par upload, faisait planter charger() avec
#  « 'dict' object has no attribute 'ndim' ».
# =============================================================================

import io
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from direction_non_vie.services.nv_triangle_validator import TriangleValidator

# Deux triangles 5×5 VOLONTAIREMENT différents : ils permettent de vérifier
# QUEL onglet a été lu, pas seulement que la lecture n'a pas planté.
COLS = ['dev0', 'dev1', 'dev2', 'dev3', 'dev4']
TRI_A = pd.DataFrame([[100., 180., 230., 260., 275.],
                      [110., 195., 250., 280., np.nan],
                      [120., 205., 265., np.nan, np.nan],
                      [130., 220., np.nan, np.nan, np.nan],
                      [125., np.nan, np.nan, np.nan, np.nan]], columns=COLS)
TRI_B = TRI_A * 2.0          # même géométrie, valeurs doubles


class _Upload(io.BytesIO):
    """Objet fichier portant un .name — équivalent d'un upload d'interface."""

    def __init__(self, donnees: bytes, nom: str):
        super().__init__(donnees)
        self.name = nom


class T1_Excel_Sans_Onglet_Nomme(unittest.TestCase):
    """Un Excel doit se charger sans qu'on ait à nommer une feuille."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='nv_val_'))
        cls.mono = cls.tmp / 'mono.xlsx'
        TRI_A.to_excel(cls.mono, index=False)
        cls.multi = cls.tmp / 'multi.xlsx'
        with pd.ExcelWriter(cls.multi) as w:           # 1re feuille = A, 2e = B
            TRI_A.to_excel(w, sheet_name='Paiements', index=False)
            TRI_B.to_excel(w, sheet_name='Charges',   index=False)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _charger(self, source, **kw):
        C, _, _, rapport = TriangleValidator(verbose=False).charger(source=source, **kw)
        return C, rapport

    def test_multi_onglets_sans_nom_onglet(self):
        """L'oracle du correctif : sans nom_onglet, on lit la PREMIÈRE feuille.
        Avant le fix : ValueError « 'dict' object has no attribute 'ndim' »."""
        C, rapport = self._charger(self.multi)
        self.assertEqual(C.shape, (5, 5))
        self.assertEqual(rapport['statut'], 'VERT')
        self.assertAlmostEqual(float(C[0, 0]), 100.0, places=2)   # feuille A, pas B
        print("    OK T1a Excel multi-onglets sans nom_onglet : 1re feuille lue (100.0)")

    def test_mono_onglet_sans_nom_onglet(self):
        """Le même défaut cassait AUSSI les fichiers à une seule feuille :
        read_excel(sheet_name=None) rend {'Sheet1': df}, pas un DataFrame."""
        C, _ = self._charger(self.mono)
        self.assertEqual(C.shape, (5, 5))
        self.assertAlmostEqual(float(C[0, 0]), 100.0, places=2)
        print("    OK T1b Excel mono-onglet sans nom_onglet : chargé")

    def test_nom_onglet_explicite_lit_le_bon_onglet(self):
        """Non-régression du cas déjà supporté — et on vérifie QUEL onglet est
        lu (valeurs doublées de la 2e feuille), pas seulement l'absence de crash."""
        C, rapport = self._charger(self.multi, nom_onglet='Charges')
        self.assertEqual(C.shape, (5, 5))
        self.assertAlmostEqual(float(C[0, 0]), 200.0, places=2)   # feuille B
        self.assertTrue(any('Charges' in str(i) for i in rapport['infos']))
        print("    OK T1c nom_onglet='Charges' : bon onglet lu (200.0) + tracé au rapport")

    def test_upload_excel_sans_nom_onglet(self):
        """Voie UPLOAD : même piège, même correctif (c'est la voie par laquelle
        un actuaire dépose un fichier depuis l'interface)."""
        for chemin, attendu, libelle in ((self.mono, 100.0, 'mono'),
                                         (self.multi, 100.0, 'multi')):
            C, _ = self._charger(_Upload(chemin.read_bytes(), chemin.name))
            self.assertEqual(C.shape, (5, 5), libelle)
            self.assertAlmostEqual(float(C[0, 0]), attendu, places=2, msg=libelle)
        # onglet nommé sur upload : toujours honoré
        C, _ = self._charger(_Upload(self.multi.read_bytes(), 'multi.xlsx'),
                             nom_onglet='Charges')
        self.assertAlmostEqual(float(C[0, 0]), 200.0, places=2)
        print("    OK T1d upload : mono et multi chargés, onglet nommé honoré")

    def test_csv_non_concerne(self):
        """Témoin : le CSV n'a jamais été touché par ce défaut."""
        csv = self.tmp / 'tri.csv'
        TRI_A.to_csv(csv, index=False)
        C, _ = self._charger(csv)
        self.assertEqual(C.shape, (5, 5))
        print("    OK T1e témoin CSV : inchangé")


if __name__ == '__main__':
    unittest.main()
