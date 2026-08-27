# -*- coding: utf-8 -*-
"""CONTRÔLES POSITIFS — C6 : les synthèses réglementaires dans TOUS les formats.

Le défaut C6 : les 7 synthèses réglementaires ne vivaient que dans l'Excel
équipe ; html / word / pdf — ce qui part au CAC — se TAISAIENT. Voie (b) :
l'orchestrateur les calcule UNE fois (patron `narration_calculee`) et les
partage à tous les formats.

⚠️ SCEAU (④). Le fragment « zone_geographique » est nommé par la synthèse
« plan amputé ». L'Excel le portait DÉJÀ (rendu en ligne, dans ses sections
natives — c'est la source de parité). La preuve du correctif : ce même fragment
atteint DÉSORMAIS html ET word, sous la section « Synthèses réglementaires ».
Second sens : la section existe (structure) ET le fond y circule (pas une
coquille vide).
"""
import io
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import openpyxl

from direction_non_vie.tarification.services import rapport_equipe_tarif as RE


def _results():
    """Un result_a6 qui DÉCLENCHE des synthèses (walk-forward indisponible,
    exclusion de conformité, plan amputé) — pour que le sceau ait à comparer."""
    r6 = {
        'success': True, 'branche': 'auto', 'statut_rag': 'AMBRE',
        'modele_production': {'modele': 'GBM'},
        'colonnes_plan_manquantes': {
            'colonnes_non_produites': ['zone_geographique', 'anciennete_permis'],
            'plan': 'auto'},
        'exclusions_conformite': {'prime_anterieure': 'variable interdite (fuite)'},
        'backtest': {}, 'audit_trail': {},
    }
    return {'a6': r6}


_FRAGMENT = 'zone_geographique'   # nommée par la synthèse « plan amputé »
_SECTION = 'Synthèses réglementaires'


def _txt_xl(blob: bytes) -> str:
    wb = openpyxl.load_workbook(io.BytesIO(blob))
    return "\n".join(str(c.value) for ws in wb.worksheets
                     for row in ws.iter_rows() for c in row if c.value is not None)


def _txt_docx(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return z.read('word/document.xml').decode('utf-8')


class TestC6_Helper(unittest.TestCase):

    def test_helper_calcule_les_syntheses_declenchees(self):
        s = RE.syntheses_reglementaires(_results())
        self.assertIn('plan_ampute', s)
        self.assertIn('walk_forward', s)
        self.assertIn(_FRAGMENT, s['plan_ampute'])

    def test_entrees_degenerees_pas_de_crash_et_walk_forward_toujours(self):
        """Sceau des gardes isinstance : a6 absent / None / liste, backtest
        non-dict → aucune exception, et walk_forward FIGURE TOUJOURS (contrôle
        positif sur l'absence : « aucune validation temporelle » vaut mieux que
        le silence)."""
        for mauvais in ({}, {'a6': None}, {'a6': ['x']},
                        {'a6': {'backtest': 'oops'}}, {'a6': {'backtest': None}}):
            s = RE.syntheses_reglementaires(mauvais)   # ne doit pas lever
            self.assertIn('walk_forward', s, f"walk_forward manque pour {mauvais!r}")


class TestC6_LesTroisFormats(unittest.TestCase):
    """⚠️ SCEAU (④) : le fond atteint html, word ET excel — plus de format muet."""

    def test_html_et_word_portent_la_section_ET_le_fond(self):
        r = _results()
        for nom, txt in (('html', RE.export_html_equipe(r)),
                         ('word', _txt_docx(RE.export_word_equipe(r)))):
            # structure : la section existe (mon correctif C6)…
            self.assertIn(_SECTION, txt, f"{nom} : section synthèses absente")
            # …et le fond y circule (second sens : pas une coquille vide)
            self.assertIn(_FRAGMENT, txt, f"{nom} : la synthèse plan amputé n'y arrive pas")

    def test_excel_source_de_parite_porte_deja_le_fond(self):
        # l'Excel rend les synthèses en ligne (pré-existant) — c'est la parité visée
        self.assertIn(_FRAGMENT, _txt_xl(RE.export_excel_equipe(_results())))

    def test_orchestrateur_calcule_une_fois_et_partage(self):
        rap = RE.generer_rapport_equipe_tarification(
            _results(), formats=['html', 'word', 'excel'])
        for nom, txt in (('html', rap['html_bytes'].decode('utf-8')),
                         ('word', _txt_docx(rap['word_bytes'])),
                         ('excel', _txt_xl(rap['excel_bytes']))):
            self.assertIn(_FRAGMENT, txt, f"{nom} (via orchestrateur) : synthèse manque")


if __name__ == '__main__':
    unittest.main(verbosity=2)
