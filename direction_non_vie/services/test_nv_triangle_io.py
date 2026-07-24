# =============================================================================
#  Tests — nv_triangle_io.py (Bloc II, module 1 : lecture universelle)
#
#  Module ISOLÉ à ce stade : branché nulle part (ni agent.py, ni façade).
#  Ces tests l'exercent donc de bout en bout sans aucune dépendance A7.
# =============================================================================

import ast
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from direction_non_vie.services.nv_triangle_io import lire_source, lister_onglets

try:                                    # moteur parquet optionnel
    import pyarrow  # noqa: F401
    _PARQUET_OK = True
except ImportError:
    try:
        import fastparquet  # noqa: F401
        _PARQUET_OK = True
    except ImportError:
        _PARQUET_OK = False

# Triangle de référence 3×3 (cumulé), réutilisé sous tous les formats.
TRI = [[100.0, 180.0, 230.0],
       [120.0, 200.0, np.nan],
       [110.0, np.nan, np.nan]]
DF_LONG = pd.DataFrame({'annee': [2015, 2016, 2017],
                        'dev_0': [100.0, 120.0, 110.0],
                        'dev_1': [180.0, 200.0, np.nan]})


class _Upload(io.BytesIO):
    """Objet fichier portant un .name — équivalent d'un upload d'interface,
    sans dépendre de Streamlit (le module doit rester agnostique)."""

    def __init__(self, donnees: bytes, nom: str):
        super().__init__(donnees)
        self.name = nom


class T1_LireSource_Formats(unittest.TestCase):
    """Chaque format supporté est lu et correctement identifié."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='nv_io_'))
        # Excel mono-onglet
        cls.xlsx = cls.tmp / 'tri.xlsx'
        DF_LONG.to_excel(cls.xlsx, index=False)
        # Excel MULTI-onglets (le piège : sheet_name=None rendrait un dict)
        cls.xlsx_multi = cls.tmp / 'multi.xlsx'
        with pd.ExcelWriter(cls.xlsx_multi) as w:
            DF_LONG.to_excel(w, sheet_name='Paiements', index=False)
            DF_LONG.to_excel(w, sheet_name='Primes',    index=False)
        # CSV (séparateur ';' — doit être détecté sans être déclaré)
        cls.csv = cls.tmp / 'tri.csv'
        DF_LONG.to_csv(cls.csv, index=False, sep=';')
        # JSON — les 3 formes du contrat
        cls.json_matrice = cls.tmp / 'matrice.json'
        cls.json_matrice.write_text(json.dumps(
            [[100, 180, 230], [120, 200, None], [110, None, None]]), encoding='utf-8')
        cls.json_records = cls.tmp / 'records.json'
        cls.json_records.write_text(json.dumps(
            [{'annee': 2015, 'dev_0': 100}, {'annee': 2016, 'dev_0': 120}]), encoding='utf-8')
        cls.json_colonnes = cls.tmp / 'colonnes.json'
        cls.json_colonnes.write_text(json.dumps(
            {'annee': [2015, 2016], 'dev_0': [100, 120]}), encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _verifier_contrat(self, r, fmt_attendu):
        """Toute lecture renvoie le même contrat SourceLue."""
        self.assertEqual(sorted(r), ['brut', 'format_fichier', 'nom_onglet', 'rapport'])
        self.assertEqual(r['format_fichier'], fmt_attendu)
        self.assertIsInstance(r['brut'], (pd.DataFrame, np.ndarray))
        self.assertIn('infos', r['rapport'])
        self.assertIn('avertissements', r['rapport'])

    def test_excel(self):
        r = lire_source(self.xlsx)
        self._verifier_contrat(r, 'excel')
        self.assertEqual(r['brut'].shape, (3, 3))
        print("    OK T1a excel : 3x3 lu")

    def test_excel_multi_onglets_ne_plante_pas(self):
        """Sans nom_onglet → PREMIÈRE feuille, jamais un dict de feuilles.
        C'est le piège qui fait planter TriangleValidator.charger()
        ('dict' object has no attribute 'ndim')."""
        r = lire_source(self.xlsx_multi)
        self._verifier_contrat(r, 'excel')
        self.assertIsInstance(r['brut'], pd.DataFrame)     # pas un dict
        # et l'onglet nommé est bien honoré
        r2 = lire_source(self.xlsx_multi, nom_onglet='Primes')
        self.assertEqual(r2['nom_onglet'], 'Primes')
        self.assertIsInstance(r2['brut'], pd.DataFrame)
        print("    OK T1b excel multi-onglets : 1re feuille par défaut, onglet nommé honoré")

    def test_csv_separateur_detecte(self):
        r = lire_source(self.csv)
        self._verifier_contrat(r, 'csv')
        self.assertEqual(r['brut'].shape[1], 3)            # ';' détecté, pas 1 colonne
        print("    OK T1c csv : séparateur ';' détecté (3 colonnes)")

    def test_json_matrice(self):
        r = lire_source(self.json_matrice)
        self._verifier_contrat(r, 'json')
        self.assertIsInstance(r['brut'], np.ndarray)       # matrice → ndarray
        self.assertEqual(r['brut'].shape, (3, 3))
        self.assertEqual(r['brut'][0, 0], 100.0)
        self.assertTrue(np.isnan(r['brut'][1, 2]))         # null → NaN
        print("    OK T1d json matrice : ndarray 3x3, null → NaN")

    def test_json_enregistrements_et_colonnes(self):
        for chemin, libelle in ((self.json_records, 'enregistrements'),
                                (self.json_colonnes, 'colonnes')):
            r = lire_source(chemin)
            self._verifier_contrat(r, 'json')
            self.assertIsInstance(r['brut'], pd.DataFrame)
            self.assertEqual(r['brut'].shape, (2, 2))
        print("    OK T1e json enregistrements + colonnes : DataFrame 2x2")

    def test_parquet_dispatch_sans_moteur(self):
        """Le dispatch .parquet et l'erreur « moteur absent » sont exercés même
        sans pyarrow/fastparquet installé — sinon ce chemin ne serait jamais
        couvert dans cet environnement."""
        chemin = self.tmp / 'factice.parquet'
        chemin.write_bytes(b'contenu-non-lu')          # seul le dispatch est testé
        with patch('pandas.read_parquet', return_value=DF_LONG) as lecteur:
            r = lire_source(chemin)
        self._verifier_contrat(r, 'parquet')
        self.assertEqual(lecteur.call_args[0][0], chemin)
        with patch('pandas.read_parquet', side_effect=ImportError('moteur')):
            with self.assertRaises(ImportError) as ctx:
                lire_source(chemin)
        self.assertIn('pyarrow', str(ctx.exception))   # message actionnable
        print("    OK T1f parquet : dispatch + erreur moteur absent (sans pyarrow)")

    @unittest.skipUnless(_PARQUET_OK, 'moteur parquet absent (pyarrow/fastparquet)')
    def test_parquet_round_trip_reel(self):
        chemin = self.tmp / 'tri.parquet'
        DF_LONG.to_parquet(chemin)
        r = lire_source(chemin)
        self._verifier_contrat(r, 'parquet')
        self.assertEqual(r['brut'].shape, (3, 3))
        print("    OK T1f-bis parquet : round-trip réel 3x3")

    def test_dataframe_array_list_dict(self):
        """Sources en mémoire : format déduit du TYPE."""
        r = lire_source(DF_LONG)
        self._verifier_contrat(r, 'dataframe')

        r = lire_source(np.array(TRI))
        self._verifier_contrat(r, 'array')
        self.assertEqual(r['brut'].shape, (3, 3))

        r = lire_source([[1.0, 2.0], [3.0, 4.0]])          # list → array
        self._verifier_contrat(r, 'array')

        for cle in ('dataframe', 'df', 'data'):            # dict façon A2
            r = lire_source({cle: DF_LONG})
            self._verifier_contrat(r, 'dict')
        print("    OK T1g mémoire : dataframe / array / list / dict (3 clés)")

    def test_upload(self):
        """Objet fichier (façon upload) : extension déduite du nom porté."""
        for chemin, libelle in ((self.xlsx, 'Excel'), (self.csv, 'CSV')):
            flux = _Upload(chemin.read_bytes(), chemin.name)
            r = lire_source(flux)
            self._verifier_contrat(r, 'upload')
            self.assertIsInstance(r['brut'], pd.DataFrame)
            self.assertEqual(r['brut'].shape[1], 3, f"upload {libelle}")
        print("    OK T1h upload : objets fichier Excel et CSV lus")


class T2_LireSource_Erreurs(unittest.TestCase):
    """Les échecs sont explicites et nomment les formats acceptés."""

    def test_erreurs_explicites(self):
        with self.assertRaises(ValueError):
            lire_source(None)
        with self.assertRaises(FileNotFoundError):
            lire_source('/chemin/inexistant/x.xlsx')
        with self.assertRaises(ValueError):
            lire_source({'inattendu': 1})                  # dict sans clé de données
        with self.assertRaises(ValueError):
            lire_source(42)                                # type non supporté
        print("    OK T2a erreurs : None / fichier absent / dict sans clé / type inconnu")

    def test_extension_inconnue_nomme_les_formats(self):
        tmp = Path(tempfile.mkdtemp(prefix='nv_io_err_'))
        try:
            mauvais = tmp / 'donnees.docx'
            mauvais.write_text('x', encoding='utf-8')
            with self.assertRaises(ValueError) as ctx:
                lire_source(mauvais)
            for ext in ('.xlsx', '.csv', '.json', '.parquet'):
                self.assertIn(ext, str(ctx.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print("    OK T2b extension inconnue : message nomme les formats acceptés")

    def test_json_structure_refusee(self):
        tmp = Path(tempfile.mkdtemp(prefix='nv_io_js_'))
        try:
            for contenu in ('42', '{"a": [1, 2], "b": [1]}'):   # scalaire / longueurs inégales
                p = tmp / 'mauvais.json'
                p.write_text(contenu, encoding='utf-8')
                with self.assertRaises(ValueError):
                    lire_source(p)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print("    OK T2c json hors contrat : scalaire et colonnes inégales refusés")


class T3_ListerOnglets(unittest.TestCase):
    """lister_onglets : les NOMS seuls, dans l'ordre du fichier."""

    def test_multi_onglets(self):
        tmp = Path(tempfile.mkdtemp(prefix='nv_io_ong_'))
        try:
            chemin = tmp / 'classeur.xlsx'
            with pd.ExcelWriter(chemin) as w:
                for nom in ('Paiements', 'Charges', 'Primes'):
                    DF_LONG.to_excel(w, sheet_name=nom, index=False)
            self.assertEqual(lister_onglets(chemin), ['Paiements', 'Charges', 'Primes'])

            csv = tmp / 'x.csv'                             # pas d'onglets hors Excel
            DF_LONG.to_csv(csv, index=False)
            with self.assertRaises(ValueError):
                lister_onglets(csv)
            with self.assertRaises(FileNotFoundError):
                lister_onglets(tmp / 'absent.xlsx')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print("    OK T3a lister_onglets : 3 noms ordonnés, CSV et fichier absent rejetés")


class T4_Perimetre(unittest.TestCase):
    """Le module ne fait QUE lire : aucune responsabilité aval, aucune UI."""

    def test_responsabilite_unique_et_agnostique(self):
        import direction_non_vie.services.nv_triangle_io as io_mod
        publiques = [n for n in dir(io_mod)
                     if not n.startswith('_') and callable(getattr(io_mod, n))
                     and getattr(getattr(io_mod, n), '__module__', '') == io_mod.__name__]
        self.assertEqual(sorted(publiques), ['lire_source', 'lister_onglets'])

        # Agnostique de l'UI : contrôle sur les IMPORTS réels (le mot peut
        # légitimement apparaître dans un commentaire), via l'AST.
        with open(io_mod.__file__, encoding='utf-8') as fh:
            texte = fh.read()
        arbre = ast.parse(texte)
        importes = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                importes.update(a.name.split('.')[0] for a in noeud.names)
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                importes.add(noeud.module.split('.')[0])
        self.assertNotIn('streamlit', importes)
        self.assertEqual(importes & {'direction_non_vie'}, set())   # aucune dépendance A7

        for interdit in ('cumsum', 'diff(', 'construire_triangle', 'SYNONYMES'):
            self.assertNotIn(interdit, texte)               # pas de logique aval

        # Le brut est rendu tel quel : aucune transformation silencieuse.
        df = pd.DataFrame({'a': [1, 2]})
        self.assertIs(lire_source(df)['brut'], df)
        print("    OK T4a périmètre : 2 fonctions publiques, sans UI ni logique aval")


if __name__ == '__main__':
    unittest.main()
