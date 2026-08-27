# -*- coding: utf-8 -*-
"""CONTRÔLES POSITIFS — Lot 1 du relevé services (C2, C3, C4, C5).

Chaque fermeture est épinglée PAR EXÉCUTION (on produit l'artefact et on lit),
avec un SECOND SENS : le faux/masqué a disparu ET le juste apparaît.

⚠️ Motif du lot, à retenir : chacun avait un cousin corrigé ailleurs (A4 pour
C3, la scorecard A3 pour C4, les KPI HTML pour C5) — jamais sur la surface qui
part au CAC. Ces tests visent CETTE surface.
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import openpyxl

from direction_non_vie.tarification.services.tarif_excel import (
    export_excel_a4, export_excel_a5)
from direction_non_vie.tarification.services import rapport_modeles_tarif as R
from direction_non_vie.tarification.a6_comparaison.test_a6_comparaison import _make_r_a4


def _texte_xl(blob: bytes) -> str:
    wb = openpyxl.load_workbook(io.BytesIO(blob))
    return "\n".join(str(c.value) for ws in wb.worksheets
                     for row in ws.iter_rows() for c in row if c.value is not None)


class TestC2_ReferenceWuthrich(unittest.TestCase):
    """C2 — l'Excel A5 citait un article de PROVISIONNEMENT chain-ladder."""

    def test_excel_a5_cite_l_article_CANN_ANCRE_a_sa_source(self):
        """La bonne réf CANN est ANCRÉE à sa source, vérifiée EN EXTERNE
        (Cambridge Core / ASTIN Bulletin, DOI 10.1017/asb.2018.42) — pas par
        simple appariement à ce que l'agent cite déjà."""
        r5 = {'success': True, 'metriques': {}, 'classement': [], 'audit_id': 'CTRL'}
        txt = _texte_xl(export_excel_a5(r5))
        self.assertIn("Yes, we CANN", txt, "la vraie référence CANN manque")
        self.assertIn("10.1017/asb.2018.42", txt,
                      "la citation n'est pas ancrée à sa source (DOI)")
        self.assertNotIn("Chain-Ladder Reserving", txt,
                         "l'article provisionnement (faux) est encore cité")


class TestC3_CompteDesModeles(unittest.TestCase):
    """C3 — « 8 modèles » figé, faux (A4 en teste ~6)."""

    def test_excel_a4_sous_titre_dynamique_et_pas_de_8_fige(self):
        r4 = _make_r_a4()
        n = len(r4['classement'])
        self.assertNotEqual(n, 8, "fixture à 8 → le test ne prouverait rien")
        txt = _texte_xl(export_excel_a4(r4))
        self.assertIn(f"{n} modèles comparés", txt)     # le vrai compte apparaît
        self.assertNotIn("×8 modèles", txt)             # le descripteur figé a disparu
        self.assertNotIn("8 modèles comparés", txt)     # le littéral figé aussi


class TestC4_H5DevianceDansLeTableau(unittest.TestCase):
    """C4 — h5_deviance, PLAFONNANTE, absente du tableau du chapitre 4."""

    @staticmethod
    def _r3(statut='ROUGE'):
        return {'success': True, 'branche': 'auto', 'metriques': {},
                'hypotheses': {'h5_deviance': {
                    'ratio_deviance_df': 1.87, 'statut': statut,
                    'message': 'Déviance/df hors bande', 'conseil': 'revoir la loi'}}}

    def test_la_ligne_H5_existe_et_porte_sa_valeur(self):
        html = R.export_html(self._r3('ROUGE'), {'success': True},
                             {'success': True},
                             narration_calculee=('Texte.', 'temoin'))
        # la ligne existe (le libellé statique)…
        self.assertIn("H5 GLM — Déviance résiduelle", html,
                      "la ligne H5 manque au tableau du chapitre 4")
        # …et la valeur mesurée y circule (second sens : pas seulement le libellé)
        self.assertIn("1.87", html, "la valeur de h5_deviance n'atteint pas le tableau")


class TestC5_MasquageParZero(unittest.TestCase):
    """C5 — `.get(clé, 0)` masquait un absent par 0.0000 dans le contexte narration."""

    def test_contexte_narration_affiche_tiret_pas_zero(self):
        # modèle de production SANS gini_test/score_global/overfit_ratio
        r6 = {'success': True, 'modele_production': {'modele': 'GBM'}}
        ctx = R._construire_contexte_tarif({'success': True}, {'success': True},
                                           r6, 'auto', '')
        self.assertIn("Gini=—", ctx)                    # absent → tiret
        self.assertNotIn("Gini=0.0000", ctx)            # jamais le zéro masquant
        self.assertNotIn("Score=0.0000", ctx)


if __name__ == '__main__':
    unittest.main(verbosity=2)
