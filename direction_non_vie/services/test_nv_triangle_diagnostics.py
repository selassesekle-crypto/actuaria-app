# =============================================================================
#  Tests — nv_triangle_diagnostics.py :: contrôle C1 (monotonie cumulée)
#
#  C1 confondait TOUTE décroissance avec une erreur de format : dès 1 % de baisse
#  il comptait une violation, et basculait ROUGE dès 3. Un RECOURS / subrogation
#  — parfaitement légitime sur un cumulé, et que tout le chantier IBNR a honoré
#  dans les cinq méthodes — coûtait donc 15 points à une donnée SAINE, avec le
#  message trompeur « vérifier le format ».
#
#  Le verdict est désormais délégué à detecter_cumulativite (SOURCE UNIQUE, module
#  de construction) : recours → AMBRE informatif, vrai mauvais format → ROUGE.
# =============================================================================

import ast
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import direction_non_vie.services.nv_triangle_diagnostics as diag
from direction_non_vie.services.nv_triangle_diagnostics import diagnostiquer_triangle
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, RAA, _TRI_RECOURS_FORT, _TRI_TOUT_DECROISSANT,
)

# Vraie erreur de format : des INCRÉMENTS bruts passés pour un cumulé.
# Décroissances fortes ET généralisées, première colonne dominante.
INCREMENTS_BRUTS = np.array([[1000., 500., 200., 80.],
                             [1100., 550., 220.,  0.],
                             [1050., 520.,   0.,  0.],
                             [1200.,   0.,   0.,  0.]])


def _c1(C, **kw):
    d = diagnostiquer_triangle(C, **kw)
    return next(c for c in d['controles'] if c['code'] == 'C1'), d


class T1_Recours_Legitime(unittest.TestCase):
    """Un recours ne doit PLUS être accusé d'être une erreur de format."""

    def test_recours_fort_ne_declenche_plus_de_faux_rouge(self):
        """Mesuré AVANT le correctif : C1 ROUGE, 0 point, score 78 = AMBRE."""
        c1, d = _c1(_TRI_RECOURS_FORT, annee_debut=2015)
        self.assertEqual(c1['statut'], 'AMBRE')          # plus ROUGE
        self.assertEqual(c1['points'], 12)               # plus 0
        self.assertEqual(d['score'], 90)                 # remonté de 78
        self.assertEqual(d['statut'], 'VERT')            # plus AMBRE
        print(f"    OK C1-a RECOURS_FORT : 78/AMBRE → {d['score']}/{d['statut']} "
              f"(C1 {c1['statut']}, {c1['points']} pts)")

    def test_tout_decroissant_idem(self):
        c1, d = _c1(_TRI_TOUT_DECROISSANT, annee_debut=2015)
        self.assertEqual(c1['statut'], 'AMBRE')
        self.assertEqual(d['statut'], 'VERT')
        print(f"    OK C1-b TOUT_DECROISSANT : 78/AMBRE → {d['score']}/{d['statut']}")

    def test_message_ne_dit_plus_verifier_le_format(self):
        """Le message doit orienter vers le recours, pas vers une fausse piste."""
        c1, _ = _c1(_TRI_RECOURS_FORT)
        self.assertIn('RECOURS', c1['message'])
        self.assertIn('légitime', c1['message'])
        self.assertNotIn('Vérifier le format', c1['message'])
        self.assertIn('À confirmer', c1['message'])      # reste un signal, pas un blanc-seing
        print("    OK C1-c message : oriente vers le recours, « à confirmer si inattendu »")

    def test_detail_des_cellules_conserve(self):
        """L'énumération cellule par cellule reste — c'est le besoin d'affichage
        propre au diagnostic, que la source unique ne fournit pas."""
        c1, _ = _c1(_TRI_RECOURS_FORT, annee_debut=2015)
        self.assertTrue(c1['detail'])
        self.assertIn('Ligne', c1['detail'][0])
        print(f"    OK C1-d détail conservé : {len(c1['detail'])} cellule(s) listée(s)")


class T2_Non_Regression_Mauvais_Format(unittest.TestCase):
    """Le correctif ne doit PAS masquer une vraie erreur de format."""

    def test_increments_bruts_restent_rouge(self):
        """Décroissances fortes ET généralisées + 1re colonne dominante =
        incréments bruts passés pour un cumulé. Doit rester ROUGE."""
        c1, d = _c1(INCREMENTS_BRUTS, annee_debut=2015)
        self.assertEqual(c1['statut'], 'ROUGE')
        self.assertEqual(c1['points'], 0)
        self.assertEqual(d['statut'], 'ROUGE')
        self.assertIn('INCRÉMENTS', c1['message'])
        self.assertIn('format', c1['message'])
        print(f"    OK C1-e incréments bruts : reste ROUGE ({d['score']}/100) — "
              f"message « format »")

    def test_triangles_sains_inchanges(self):
        for nom, T, score in (('GenIns', GENINS, 100), ('RAA', RAA, 92)):
            c1, d = _c1(T, annee_debut=2015)
            self.assertEqual(c1['statut'], 'VERT', nom)
            self.assertEqual(c1['points'], 15, nom)
            self.assertEqual(d['score'], score, nom)
        print("    OK C1-f triangles sains : GenIns 100, RAA 92 — strictement inchangés")

    def test_les_trois_cas_sont_distingues(self):
        """La distinction en un coup d'œil : sain / recours / mauvais format."""
        verdicts = {nom: _c1(T)[0]['statut'] for nom, T in (
            ('sain', GENINS), ('recours', _TRI_RECOURS_FORT),
            ('mauvais format', INCREMENTS_BRUTS))}
        self.assertEqual(verdicts, {'sain': 'VERT', 'recours': 'AMBRE',
                                    'mauvais format': 'ROUGE'})
        print(f"    OK C1-g trois cas distingués : {verdicts}")


class T3_Source_Unique(unittest.TestCase):
    """La logique n'est PAS dupliquée : elle est déléguée."""

    def test_verdict_delegue_a_la_source_unique(self):
        """Un espion prouve que le verdict vient bien de detecter_cumulativite."""
        with patch.object(diag, '_verdict_cumulativite',
                          return_value='incremental') as espion:
            c1, _ = _c1(_TRI_RECOURS_FORT)
        espion.assert_called()
        self.assertEqual(c1['statut'], 'ROUGE')   # le verdict simulé pilote bien C1
        print("    OK C1-h verdict délégué : la source unique pilote le statut")

    def test_aucune_regle_de_seuil_recopiee(self):
        """AST : les seuils de detecter_cumulativite (0.8 / 0.30 / 0.5) ne doivent
        pas réapparaître dans le diagnostic — sinon les deux dériveraient."""
        src = Path(diag.__file__).read_text(encoding='utf-8')
        arbre = ast.parse(src)
        for n in ast.walk(arbre):
            if not (isinstance(n, ast.FunctionDef) and n.name == '_ctrl_monotonie'):
                continue
            constantes = {c.value for c in ast.walk(n)
                          if isinstance(c, ast.Constant) and isinstance(c.value, float)}
            for seuil in (0.8, 0.30, 0.5):
                self.assertNotIn(seuil, constantes,
                                 f"seuil {seuil} recopié depuis detecter_cumulativite")
        print("    OK C1-i AST : aucun seuil de la source unique recopié dans C1")

    def test_degradation_propre_si_source_indisponible(self):
        """Sans le module de construction, le verdict prudent 'ambigu' — jamais
        une accusation à tort, jamais un crash."""
        with patch.dict('sys.modules',
                        {'direction_non_vie.services.nv_triangle_construction': None}):
            self.assertEqual(diag._verdict_cumulativite(INCREMENTS_BRUTS), 'ambigu')
        print("    OK C1-j source indisponible : repli 'ambigu' (prudent), pas de crash")


if __name__ == '__main__':
    unittest.main()
