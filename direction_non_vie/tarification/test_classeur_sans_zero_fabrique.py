r"""
==============================================================================
  UN CLASSEUR SIGNE N'INVENTE NI UN ZERO NI UN VERT
==============================================================================

⚠️⚠️ `TE-D1` -- LE CLASSEUR A4 PUBLIAIT << Score global = 0 >> SUR CHAQUE
LIGNE. `round(m.get('score_global', 0), 4)` rendait `0.0000` sous
l'en-tete << Score global >>, dans une section intitulee
<< CLASSEMENT MULTICRITERES (Gini 40 % / Stabilite 30 % / Interpret.
20 % / RMSE 10 %) >>. *Le classeur que l'actuaire signe affirmait donc
que TOUS les candidats scorent zero sur une grille qu'aucun d'eux n'a
passee.*

A4 ne pose JAMAIS `score_global` -- releve AST du 14/09 : 0 occurrence
dans ses 4 132 lignes. Mesure sur le classeur produit :

    avant   colonne 7 : ('0', '0.0000') x3
    apres   colonne 7 : ('non mesure', 'General') x3

⚠️ ET LE FORMAT SUIT LA VALEUR : un mot ne se formate pas en `0.0000`.

⚠️⚠️ `TE-D2` -- DEUX ONGLETS DU MEME CLASSEUR SE CONTREDISAIENT SUR LA
MEME ABSENCE. Sur un `result_a1` DEPOURVU de bloc `qualite`, l'onglet 1
publiait << non transmis >> NEUF fois en AMBRE, et l'onglet 2 publiait
<< Aucune anomalie detectee >> et << Alertes : Aucune >> avec DEUX
pastilles VERTES (fond 2ECC71). *Un lecteur y voyait un fichier
parfait ; il n'y avait pas de fichier.*

⚠️⚠️ ET UN TROISIEME ONGLET PORTAIT LE MEME DEFAUT, QUE L'AUDITEUR NE
NOMME PAS. L'onglet 3 affirmait << Aucune coercition necessaire (types
deja corrects) >> en VERT sur la meme absence. Mesure du 14/09, meme
classeur, meme entree :

    avant   onglet 1 : non transmis x9, 0 pastille verte
            onglet 2 : non transmis x0, 2 pastilles VERTES
            onglet 3 : non transmis x0, 2 pastilles VERTES
    apres   onglet 1 : x9  |  onglet 2 : x2  |  onglet 3 : x2
            0 pastille verte dans TOUT le classeur

⚠️ ON NE REMPLACE PAS UN VERT LEGITIME PAR UN AMBRE. `ZF-4` tient ce
point : avec un bloc `qualite` SAIN et zero anomalie, le
<< Aucune anomalie detectee >> VERT revient. *L'erreur miroir
effacerait un fait au lieu d'en inventer un.*
==============================================================================
"""
from __future__ import annotations

import ast
import io
import logging
import os
import pathlib
import sys
import unittest
import warnings

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from core.conformite_reglementaire import NON_MESURE, NON_TRANSMIS
from direction_non_vie.tarification.services import tarif_excel as TE

_SOURCE = (_RACINE / 'direction_non_vie' / 'tarification' / 'services'
           / 'tarif_excel.py')
#: Le vert de la charte -- c'est LUI qu'une absence ne doit jamais porter.
_VERT = '2ECC71'
#: ⚠️⚠️ MESURE DU 14/09, ET ELLE EST BIEN PLUS LARGE QUE LE CONSTAT RECU.
#: J'attendais TROIS autres sites -- c'est ce que donnait un grep sur
#: `score_global` seul. Le releve AST, qui porte sur la FORME
#: `round(x.get(cle, <nombre>), n)` et non sur un nom de cle, en trouve
#: DOUZE : `k`, `z_moyen`, `mu_marche`, `sigma2_intra`, `sigma2_entre`,
#: `mu_global`, `interpretabilite` (x2), `score_global` (x2),
#: `gini_wf_moyen`, et le `score_global` de la qualite A1.
#: *Chacun publie un zero que personne n'a mesure, dans un classeur
#: signe.* `TE-D1` n'etait donc pas un cas isole : c'etait un exemplaire.
#: `ZF-5` les COMPTE et MORD si leur nombre augmente -- il ne les ferme
#: pas ; c'est un constat de ce chantier, nomme et non traite.
_AUTRES_SITES_ZERO = 12


def _cellules(octets) -> list:
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(octets))
    out = []
    for ws in wb.worksheets:
        for ligne in ws.iter_rows():
            for c in ligne:
                if c.value is None:
                    continue
                try:
                    fond = (c.fill.fgColor.rgb
                            if c.fill and c.fill.fgColor else None)
                except Exception:                             # noqa: BLE001
                    fond = None
                out.append((ws.title, c.row, c.column, str(c.value),
                            c.number_format, str(fond or '')))
    return out


def _classement(avec_score: bool) -> dict:
    entree = {'modele': 'xgboost', 'famille': 'ml', 'gini_test': 0.9062,
              'gini_train': 0.92, 'overfit_ratio': 1.11, 'rmse_test': 42.0,
              'mae_test': 31.0, 'overfit_alerte': False,
              'recommandation': 'retenu'}
    if avec_score:
        entree = dict(entree, score_global=0.8741)
    return {'success': True, 'statut_rag': 'VERT', 'branche': 'auto',
            'classement': [entree, dict(entree, modele='lightgbm')],
            'metriques': {}, 'meilleur_modele': 'xgboost'}


def _a1(qualite) -> dict:
    return {'success': True, 'statut_rag': 'AMBRE', 'branche': 'auto',
            'sous_branche': 'auto', 'qualite': qualite, 'rapport': {}}


_QUALITE_SAINE = {'score_global': 91.2, 'nb_lignes': 700, 'nb_colonnes': 14,
                  'taux_completude': 99.13, 'nb_doublons': 0,
                  'taux_doublons': 0.0, 'expo_ok_pct': 98.51,
                  'granularite': 'contrat', 'nb_types_aberrants': 0,
                  'aberrants': {}, 'alertes_aberrants': [], 'colonnes': []}


class TestClasseurSansZeroFabrique(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._journal = logging.getLogger()
        cls._niveau = cls._journal.level
        cls._journal.setLevel(logging.CRITICAL)
        warnings.filterwarnings('ignore')

    @classmethod
    def tearDownClass(cls):
        cls._journal.setLevel(cls._niveau)

    def _colonne_score(self, avec_score):
        octets = TE.export_excel_a4(_classement(avec_score), audit_id='ZF')
        self.assertTrue(octets, 'le classeur A4 ne sort pas')
        cellules = _cellules(octets)
        entete = [(f, lg, col) for f, lg, col, v, _, _ in cellules
                  if v == 'Score global']
        self.assertEqual(
            len(entete), 1,
            f"l'en-tete « Score global » n'est plus unique : {entete}")
        f, lg, col = entete[0]
        return [(v, fmt) for ff, ll, cc, v, fmt, _ in cellules
                if ff == f and cc == col and lg < ll <= lg + 2]

    # ── ZF-1 ─────────────────────────────────────────────────────────────
    def test_ZF1_un_score_ABSENT_ne_devient_plus_un_zero(self):
        """⚠️ LE FORMAT COMPTE AUTANT QUE LA VALEUR : `0.0000` sur un mot
        serait la meme affirmation, ecrite autrement."""
        vues = self._colonne_score(avec_score=False)
        self.assertEqual(
            len(vues), 2,
            f"le classement ne publie plus deux lignes : {vues}")
        self.assertEqual(
            [v for v, _ in vues], [NON_MESURE, NON_MESURE],
            f"le classeur A4 signe publie encore un score sur un classement "
            f"qui n'en porte aucun : {vues}")
        formats = {fmt for _, fmt in vues}
        self.assertNotIn(
            'FMT_DEC4', formats,
            "un mot porte un format decimal")
        self.assertEqual(
            [f for f in formats if '0.0000' in str(f)], [],
            f"un mot est formate en decimales : {formats}")
        print(f"    ZF-1 SCEAU : score absent -> {vues}")

    # ── ZF-2 ─────────────────────────────────────────────────────────────
    def test_ZF2_un_score_PRESENT_reste_un_nombre_formate(self):
        """La contre-epreuve : le cas DEJA CORRECT ne bouge pas."""
        vues = self._colonne_score(avec_score=True)
        self.assertEqual(
            [v for v, _ in vues], ['0.8741', '0.8741'],
            f"un score REMIS n'atteint plus le classeur : {vues}")
        self.assertTrue(
            all('0.0000' in str(fmt) for _, fmt in vues),
            f"un score remis a perdu son format decimal : {vues}")
        print(f"    ZF-2 SCEAU : score present -> {vues}")

    # ── ZF-3 ─────────────────────────────────────────────────────────────
    def test_ZF3_une_ABSENCE_ne_porte_AUCUNE_pastille_verte(self):
        """⚠️⚠️ LE RELEVE PORTE SUR TOUT LE CLASSEUR, pas sur l'onglet 2 :
        c'est ainsi que le troisieme onglet est apparu."""
        cellules = _cellules(TE.export_excel_a1(_a1({}), audit_id='ZF'))
        verts = [(f, lg, v) for f, lg, _, v, _, fond in cellules
                 if _VERT in fond.upper()]
        self.assertEqual(
            verts, [],
            f"{len(verts)} pastille(s) VERTE(S) sur un classeur dont le bloc "
            f"`qualite` n'est jamais arrive : {verts[:4]}. Un lecteur y voit "
            f"un fichier parfait ; il n'y a pas de fichier.")
        par_onglet = {}
        for f, _, _, v, _, _ in cellules:
            if NON_TRANSMIS in str(v).lower():
                par_onglet[f] = par_onglet.get(f, 0) + 1
        muets = [f for f in ('2-Aberrants', '3-Coercition Types')
                 if not par_onglet.get(f)]
        self.assertEqual(
            muets, [],
            f"{muets} ne publie(nt) pas « {NON_TRANSMIS} » sur une absence : "
            f"il(s) se tai(sen)t la ou l'onglet 1 parle. Comptes : "
            f"{par_onglet}")
        print(f"    ZF-3 SCEAU : 0 pastille verte, « {NON_TRANSMIS} » par "
              f"onglet -> {par_onglet}")

    # ── ZF-4 ─────────────────────────────────────────────────────────────
    def test_ZF4_un_VERT_LEGITIME_revient_sur_un_bloc_sain(self):
        """⚠️⚠️ L'ERREUR MIROIR. Remplacer tout vert par un ambre effacerait
        un fait au lieu d'en inventer un. Avec un bloc `qualite` SAIN et
        zero anomalie, le « Aucune anomalie detectee » VERT doit revenir."""
        cellules = _cellules(TE.export_excel_a1(_a1(dict(_QUALITE_SAINE)),
                                                audit_id='ZF'))
        textes = [v for _, _, _, v, _, _ in cellules]
        self.assertTrue(
            [t for t in textes if 'Aucune anomalie' in t],
            "le « Aucune anomalie detectee » a disparu d'un bloc SAIN : le "
            "correctif a deborde sur le cas deja correct")
        verts = [v for _, _, _, v, _, fond in cellules
                 if _VERT in fond.upper()]
        self.assertTrue(
            verts,
            "aucune pastille verte sur un bloc qualite SAIN : le classeur "
            "ne sait plus dire qu'il a cherche et n'a rien trouve")
        #: ⚠️⚠️ L'ASSIETTE PORTE SUR L'ONGLET DU BLOC TESTE, PAS SUR TOUT LE
        #: CLASSEUR. Ma premiere version exigeait zero « non transmis »
        #: PARTOUT : elle accusait a tort, parce que la fixture ne porte
        #: pas de bloc `coercition` et que l'onglet 3 le DIT -- ce qui est
        #: exactement le comportement voulu. *Les deux blocs sont
        #: independants ; un controle qui les confond mesure autre chose
        #: que ce qu'il annonce.*
        sur_aberrants = [v for f, _, _, v, _, _ in cellules
                         if f == '2-Aberrants'
                         and NON_TRANSMIS in str(v).lower()]
        self.assertEqual(
            sur_aberrants, [],
            f"l'onglet des aberrants publie « {NON_TRANSMIS} » sur un bloc "
            f"`qualite` SAIN : le correctif a deborde sur le cas deja "
            f"correct.")
        print(f"    ZF-4 SCEAU : bloc sain -> {len(verts)} pastille(s) "
              f"verte(s) legitime(s), 0 « {NON_TRANSMIS} » a l'onglet 2")

    # ── ZF-5 ─────────────────────────────────────────────────────────────
    def test_ZF5_LES_AUTRES_sites_du_zero_fabrique_sont_COMPTES(self):
        """⚠️ CE CONTROLE NE FERME RIEN : il MESURE et PUBLIE. Trois autres
        sites de ce fichier portent encore
        `round(x.get('score_global', <nombre>), n)`. Ils ne sont pas le
        constat de l'auditeur et ne sont pas traites ici -- *il MORD si
        leur nombre augmente.*"""
        arbre = ast.parse(_SOURCE.read_bytes().decode('utf-8'))
        sites = []
        for n in ast.walk(arbre):
            if not (isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name) and n.func.id == 'round'):
                continue
            if not n.args:
                continue
            interieur = n.args[0]
            if (isinstance(interieur, ast.Call)
                    and isinstance(interieur.func, ast.Attribute)
                    and interieur.func.attr == 'get'
                    and len(interieur.args) == 2
                    and isinstance(interieur.args[1], ast.Constant)
                    and isinstance(interieur.args[1].value, (int, float))):
                sites.append((n.lineno, ast.unparse(n)[:56]))
        self.assertLessEqual(
            len(sites), _AUTRES_SITES_ZERO,
            f"le nombre de `round(x.get(cle, <nombre>), n)` a AUGMENTE : "
            f"{sites}. Il valait {_AUTRES_SITES_ZERO} au 14/09/2026, et "
            f"chacun peut publier un zero que personne n'a mesure.")
        print(f"    ZF-5 RELEVE (non ferme) : {len(sites)} site(s) de zero "
              f"fabrique restants -> {[lg for lg, _ in sites]}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
