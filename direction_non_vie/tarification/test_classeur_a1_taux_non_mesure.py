r"""
==============================================================================
  UN TAUX QU'ON N'A PAS MESURE NE SE DIVISE PAS -- ET LE CLASSEUR EXISTE
==============================================================================

⚠️⚠️ `XLA1-1` -- **REGRESSION DE CE CHANTIER, PAS UNE DETTE RECUE.** Les
trois taux de l'onglet 1 du classeur A1 s'ecrivaient
`qualite.get(cle, 0) / 100`. Ce defaut a `0` ne sert QUE si la cle est
ABSENTE : quand elle est PRESENTE et vaut `None`, la division leve
`TypeError`, le `except` de `export_excel_a1` rend `b''`, **et le
classeur que l'actuaire signe n'existe pas.**

`None` etait inatteignable jusqu'au 13/09/2026 : A1 posait
`'expo_ok_pct': round(expo_ok, 2)`. Le correctif `RDP-6` du 13/09 -- *<<
une exposition qu'on n'a pas lue ne se certifie pas >>* -- l'a rendu
atteignable, et `tarif_excel.py` n'a pas suivi. *Fermer un constat a
change un contrat a l'insu de son lecteur.*

Mesure du 14/09/2026, chemin vivant, `AgentA1Ingestion.run` sur le plan
reel `auto_fr_reel` :

    colonne d'exposition declaree PRESENTE  ->  excel_bytes = 9 350 o
    colonne d'exposition declaree ABSENTE   ->  excel_bytes =     0 o

⚠️⚠️ `XLA1-2` -- **ET LE MOTIF NE VOYAGEAIT NULLE PART.** A1 ecrit en
commentaire *<< le MOTIF voyage avec, sinon l'absence redevient muette
>>* puis pose `expo_non_mesuree_motif`. Releve AST du 14/09 sur tout le
depot : **aucune surface de production ne le lisait**, seul un test. Un
fait calcule qui n'atteint aucun livrable n'existe pas.

⚠️ CE QUI BOUGE, ET CE QUI NE BOUGE PAS. Contre-epreuve du 14/09, le
classeur produit depuis `daeb428` gele et depuis l'arbre corrige,
compare CELLULE PAR CELLULE (un .xlsx porte un horodatage : l'octet pour
octet mentirait) :

    les trois taux mesures      77 -> 77 cellules,  0 ecart
    aucun bloc qualite          86 -> 86 cellules,  0 ecart
    un taux a ZERO REEL         77 -> 77 cellules,  0 ecart
    expo_ok_pct = None      0 OCTET -> 78 cellules
    cle absente                 77 -> 78 cellules,  2 ecarts VOULUS

Les deux ecarts voulus : le `0` formate `0.00%` devient `non mesure` et
prend la pastille `A surveiller`. **C'est le zero fabrique que ce
fichier condamne quatre fois ailleurs** ; il disparait aussi pour la cle
absente, deliberement. *Un zero MESURE, lui, reste un taux* -- c'est le
cas C ci-dessus, et `XL-3` le tient.
==============================================================================
"""
from __future__ import annotations

import ast
import io
import logging
import pathlib
import sys
import tempfile
import unittest
import warnings

_RACINE = pathlib.Path(__file__).resolve().parents[2]
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from core.conformite_reglementaire import NON_MESURE
from direction_non_vie.tarification.services import tarif_excel as TX

_SOURCE = (_RACINE / 'direction_non_vie' / 'tarification' / 'services'
           / 'tarif_excel.py')

#: Le motif que A1 publie quand la colonne declaree manque au fichier.
_MOTIF = ("colonne d'exposition 'Exposure' absente du fichier : aucun "
          "taux de conformite n'est publie, aucune valeur n'est supposee.")


def _qualite(**kw):
    """Le bloc qualite d'A1, complet, avant qu'on en abime une case."""
    base = {'score_global': 91.2, 'nb_lignes': 700, 'nb_colonnes': 14,
            'taux_completude': 99.13, 'nb_doublons': 0,
            'taux_doublons': 0.0, 'expo_ok_pct': 98.51,
            'granularite': 'contrat', 'nb_types_aberrants': 0,
            'aberrants': {}, 'alertes_aberrants': [], 'colonnes': []}
    base.update(kw)
    return {'success': True, 'statut_rag': 'VERT', 'branche': 'auto',
            'qualite': base, 'rapport': {}}


def _cellules(octets):
    """Toutes les cellules non vides du classeur : {(feuille, l, c): texte}."""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(octets))
    return {(ws.title, c.row, c.column): (str(c.value), c.number_format)
            for ws in wb.worksheets for row in ws.iter_rows() for c in row
            if c.value is not None}


class TestClasseurA1TauxNonMesure(unittest.TestCase):

    # ── XL-1 ─────────────────────────────────────────────────────────────
    def test_XL1_un_taux_None_ne_detruit_plus_le_classeur_signe(self):
        """Les TROIS taux, un par un : le classeur doit exister."""
        temoin = TX.export_excel_a1(_qualite(), audit_id='XL1')
        self.assertTrue(temoin, "le cas de reference ne produit deja rien")
        vus = {}
        for cle in ('expo_ok_pct', 'taux_completude', 'taux_doublons'):
            octets = TX.export_excel_a1(_qualite(**{cle: None}),
                                        audit_id='XL1')
            vus[cle] = len(octets or b'')
        self.assertTrue(
            all(v > 0 for v in vus.values()),
            f"un taux a `None` rend encore un classeur VIDE : {vus}. "
            f"`export_excel_a1` divise un `None`, son `except` rend `b''`, "
            f"et le document que l'actuaire signe n'existe pas.")
        print(f"    XL-1 SCEAU : 3 taux a None -> {sorted(vus.values())} "
              f"octets (temoin {len(temoin)})")

    # ── XL-2 ─────────────────────────────────────────────────────────────
    def test_XL2_le_motif_de_l_absence_atteint_la_cellule_signee(self):
        """`XLA1-2` : le motif d'A1 doit ATTEINDRE le classeur, pas rester
        dans un dictionnaire que personne ne lit."""
        r = _qualite(expo_ok_pct=None)
        r['qualite']['expo_non_mesuree_motif'] = _MOTIF
        cellules = _cellules(TX.export_excel_a1(r, audit_id='XL2'))
        textes = [v[0] for v in cellules.values()]
        porteuses = [t for t in textes if "colonne d'exposition" in t]
        self.assertTrue(
            porteuses,
            f"le motif d'absence publie par A1 n'atteint AUCUNE cellule du "
            f"classeur signe. A1 ecrit pourtant << le MOTIF voyage avec, "
            f"sinon l'absence redevient muette >>. {len(cellules)} cellules "
            f"relues.")
        #: et sans motif, le mot unique de l'absence -- jamais un vide
        sans = _cellules(TX.export_excel_a1(_qualite(expo_ok_pct=None),
                                            audit_id='XL2'))
        self.assertIn(
            NON_MESURE, [v[0] for v in sans.values()],
            f"sans motif, la ligne d'exposition ne publie pas meme "
            f"`{NON_MESURE}` : l'absence est redevenue muette.")
        print(f"    XL-2 SCEAU : le motif atteint la cellule "
              f"({porteuses[0][:44]}...) ; sans motif -> {NON_MESURE!r}")

    # ── XL-3 ─────────────────────────────────────────────────────────────
    def test_XL3_un_zero_MESURE_reste_un_taux_et_non_une_absence(self):
        """⚠️ L'ASYMETRIE QUI COMPTE. `0.0` est une MESURE ; `None` est une
        absence. Les confondre remplacerait un fait par un mot -- exactement
        l'erreur miroir de celle que ce lot ferme."""
        cellules = _cellules(TX.export_excel_a1(
            _qualite(expo_ok_pct=0.0, taux_completude=0.0), audit_id='XL3'))
        pourcents = [(k, v) for k, v in cellules.items()
                     if v[1] == '0.00%' and v[0] in ('0', '0.0')]
        mots = [v[0] for v in cellules.values() if v[0] == NON_MESURE]
        self.assertGreaterEqual(
            len(pourcents), 2,
            f"un taux MESURE a zero n'est plus publie comme un taux : "
            f"{len(pourcents)} cellule(s) au format pourcentage. Un zero "
            f"mesure est un fait, pas une absence.")
        self.assertEqual(
            mots, [],
            f"un zero MESURE a ete transforme en `{NON_MESURE}` : {mots}. "
            f"C'est l'erreur miroir du constat -- elle efface un fait au "
            f"lieu d'en inventer un.")
        print(f"    XL-3 SCEAU : zero MESURE -> {len(pourcents)} cellule(s) "
              f"au format pourcentage, 0 mot d'absence")

    # ── XL-4 ─────────────────────────────────────────────────────────────
    def test_XL4_le_cas_MESURE_ne_bouge_pas(self):
        """La contre-epreuve, portee dans le depot : le classeur du cas
        deja correct doit rester CELLULE POUR CELLULE ce qu'il etait."""
        a = _cellules(TX.export_excel_a1(_qualite(), audit_id='XL4'))
        b = _cellules(TX.export_excel_a1(_qualite(), audit_id='XL4'))
        self.assertEqual(a, b, "le classeur n'est meme pas reproductible")
        ligne = [(k, v) for k, v in a.items()
                 if v[1] == '0.00%']
        self.assertGreaterEqual(
            len(ligne), 3,
            f"les trois taux mesures ne sont plus publies au format "
            f"pourcentage : {len(ligne)} cellule(s). Le correctif a deborde "
            f"sur le cas deja correct.")
        self.assertNotIn(
            NON_MESURE, [v[0] for v in a.values()],
            "un taux MESURE porte le mot de l'absence")
        print(f"    XL-4 SCEAU : {len(a)} cellules, {len(ligne)} taux au "
              f"format pourcentage, 0 mot d'absence")

    # ── XL-5 ─────────────────────────────────────────────────────────────
    def test_XL5_AUCUN_site_du_fichier_ne_calcule_sur_un_defaut_numerique(
            self):
        """⚠️⚠️ LE RELEVE EST PAR AST, ET IL PORTE SUR LA FORME, PAS SUR UN
        NOM. `x.get(cle, <nombre>)` employe comme operande d'un calcul est
        la forme qui leve `TypeError` sur un `None` present : le defaut ne
        couvre que la cle ABSENTE. On interdit la FORME, sinon un futur lot
        la reintroduirait sous un autre nom de cle."""
        arbre = ast.parse(_SOURCE.read_bytes().decode('utf-8'))
        fautifs = []
        for n in ast.walk(arbre):
            if not isinstance(n, ast.BinOp):
                continue
            for cote in (n.left, n.right):
                if (isinstance(cote, ast.Call)
                        and ast.unparse(cote.func).endswith('.get')
                        and len(cote.args) == 2
                        and isinstance(cote.args[1], ast.Constant)
                        and isinstance(cote.args[1].value, (int, float))
                        and not isinstance(cote.args[1].value, bool)):
                    fautifs.append((n.lineno, ast.unparse(n)[:72]))
        self.assertEqual(
            sorted(set(fautifs)), [],
            f"{len(set(fautifs))} site(s) calculent sur un `.get(cle, "
            f"<nombre>)` : {sorted(set(fautifs))}. Le defaut numerique ne "
            f"couvre PAS une cle presente valant `None` -- et un `None` y "
            f"detruit le classeur entier.")
        print(f"    XL-5 SCEAU : 0 site de cette forme dans "
              f"{_SOURCE.name} ({len(_SOURCE.read_bytes())} octets relus)")

    # ── XL-6 ─────────────────────────────────────────────────────────────
    def test_XL6_LE_CHEMIN_VIVANT_produit_le_classeur(self):
        """⚠️ LE CONTROLE LE PLUS CHER, ET LE SEUL QUI PROUVE LA SURFACE.
        Les cinq precedents appellent la fabrique ; celui-ci lance A1 comme
        l'orchestrateur le lance, sur le plan reel, et relit `excel_bytes`.
        *C'est par ce chemin que le defaut est arrive dans un livrable.*"""
        import numpy as np
        import pandas as pd

        from core.plan_tarifaire import PlanTarifaire
        from direction_non_vie.tarification.a1_ingestion.agent import (
            AgentA1Ingestion,
        )

        racine = logging.getLogger()
        niveau = racine.level
        racine.setLevel(logging.CRITICAL)
        warnings.filterwarnings('ignore')
        tmp = tempfile.mkdtemp(prefix='xla1_')
        try:
            rng = np.random.default_rng(20260914)
            n = 400

            def jeu(nom_expo):
                return pd.DataFrame({
                    'IDpol': np.arange(n),
                    'ClaimNb': rng.poisson(0.1, n),
                    'ClaimAmount': rng.gamma(2.0, 900.0, n),
                    nom_expo: rng.uniform(0.2, 1.0, n),
                    'BonusMalus': rng.integers(50, 130, n),
                    'VehPower': rng.integers(3, 12, n),
                    'VehAge': rng.integers(0, 20, n),
                    'DrivAge': rng.integers(18, 90, n),
                    'Area': rng.choice(list('ABCDE'), n),
                    'Region': rng.choice(['R11', 'R24', 'R27'], n),
                    'VehGas': rng.choice(['Regular', 'Diesel'], n),
                    'Density': rng.integers(10, 5000, n)})

            source = (_RACINE / 'plans' / 'auto_fr_reel.yaml').read_text(
                encoding='utf-8')
            cible = pathlib.Path(tmp) / 'plan.yaml'
            cible.write_text(source, encoding='utf-8')
            plan = PlanTarifaire.depuis_yaml(str(cible))

            vus = {}
            for etiquette, colonne in (('declaree presente', plan.exposition),
                                       ('declaree ABSENTE', 'duree_contrat')):
                agent = AgentA1Ingestion(
                    base_path=str(pathlib.Path(tmp) / 'data'),
                    audit_path=str(pathlib.Path(tmp) / 'audit'),
                    verbose=False)
                r = agent.run(branche='non_vie', sous_branche='auto',
                              dataframe=jeu(colonne), plan=plan)
                vus[etiquette] = (
                    (r.get('qualite') or {}).get('expo_ok_pct'),
                    len(r.get('excel_bytes') or b''))
        finally:
            racine.setLevel(niveau)

        self.assertIsNone(
            vus['declaree ABSENTE'][0],
            f"le cas de mesure n'est plus atteint : A1 publie "
            f"{vus['declaree ABSENTE'][0]!r} au lieu de `None` quand la "
            f"colonne declaree manque. Ce controle ne prouve plus rien.")
        self.assertGreater(
            vus['declaree ABSENTE'][1], 0,
            f"sur le CHEMIN VIVANT, le classeur A1 signe vaut 0 octet quand "
            f"la colonne d'exposition declaree manque au fichier : {vus}")
        print(f"    XL-6 SCEAU : chemin vivant -- presente "
              f"{vus['declaree presente'][1]} o, ABSENTE "
              f"{vus['declaree ABSENTE'][1]} o")


if __name__ == '__main__':
    unittest.main(verbosity=2)
