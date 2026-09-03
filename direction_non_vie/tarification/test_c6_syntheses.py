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
import re
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


#: ⚠️ UN JEU OU LE STATUT CONSOLIDE NE COINCIDE AVEC AUCUN STATUT D'AGENT.
#: `_collecter_statuts` ne retient que les agents `success` ; sans aucun, la
#: liste est vide et `_statut_global([])` rend AMBRE, tandis que les six
#: lignes du tableau par agent affichent « N/A ». C'est ce qui rend le sceau
#: possible : chercher « AMBRE » dans le document avec le jeu ordinaire
#: passerait SANS le correctif, puisque le tableau le porte deja.
def _results_aucun_agent_abouti():
    return {'a6': {'success': False, 'branche': 'auto', 'statut_rag': 'VERT'}}


def _results_un_agent_rouge():
    return {'a3': {'success': True, 'statut_rag': 'ROUGE', 'branche': 'auto'},
            'a6': {'success': True, 'statut_rag': 'VERT', 'branche': 'auto'}}


def _paragraphes_docx(blob: bytes):
    """Le texte du .docx, PARAGRAPHE PAR PARAGRAPHE.

    ⚠️ On ne se contente pas de chercher une chaine dans tout le document :
    le tableau par agent porte deja des mots de statut, et un controle qui
    cherche « AMBRE » n'importe ou passerait sans le correctif. Un libelle
    et sa valeur doivent etre dans le MEME paragraphe pour prouver qu'ils
    sont publies ENSEMBLE.
    """
    xml = _txt_docx(blob)
    paras = []
    for bloc in re.findall(r'<w:p[ >].*?</w:p>', xml, re.DOTALL):
        paras.append(''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', bloc,
                                        re.DOTALL)))
    return paras


_LIBELLE_CONSOLIDE = 'Statut consolidé'


class TestSTC_LeStatutConsolideDansTousLesFormats(unittest.TestCase):
    """⚠️⚠️ LE WORD CALCULAIT LE STATUT CONSOLIDE PUIS LE JETAIT.

    Mesure du 03/09/2026, sur le depot a `ff5c9c0` :

      export Excel  L300 : _kpi(..., "Statut consolidé", statut_global)
      export HTML   L736 : <span class="badge...">{statut_global}</span>
      export WORD   L822 : statut_global = _statut_global(...)  -> JAMAIS ECRIT

    `statut_rgb`, definie juste au-dessus dans la meme fonction, n'etait
    appelee nulle part : le bloc etait prevu et n'a jamais ete ecrit. Le Word
    est le format qui CIRCULE -- c'est celui qui partait sans la synthese.

      *Un format muet la ou ses voisins parlent est un ecart, pas un choix.*

    C'est le meme defaut que `C6` au-dessus, sur une autre grandeur : d'ou
    ce fichier plutot qu'un nouveau.
    """

    def test_stc_1_le_word_publie_le_libelle_ET_la_valeur_ensemble(self):
        """STC-1 : libelle et valeur dans le MEME paragraphe."""
        paras = _paragraphes_docx(
            RE.export_word_equipe(_results_aucun_agent_abouti()))
        porteurs = [p for p in paras if _LIBELLE_CONSOLIDE in p]
        self.assertTrue(
            porteurs,
            f"le Word ne publie pas « {_LIBELLE_CONSOLIDE} » : "
            f"{[p[:60] for p in paras[:8]]}")
        self.assertTrue(
            any('AMBRE' in p for p in porteurs),
            f"le libelle est present mais SANS sa valeur : {porteurs}")

    def test_stc_2_les_trois_formats_portent_le_statut_consolide(self):
        """STC-2 : L'ASSIETTE -- parite des trois formats.

        ⚠️ Le jeu n'a AUCUN agent abouti : le consolide vaut AMBRE et le
        tableau par agent n'affiche que « N/A ». Toute occurrence d'AMBRE
        dans un document vient donc de la publication du consolide, et de
        rien d'autre.
        """
        r = _results_aucun_agent_abouti()
        formats = (
            ('excel', _txt_xl(RE.export_excel_equipe(r))),
            ('html', RE.export_html_equipe(r)),
            ('word', _txt_docx(RE.export_word_equipe(r))),
        )
        muets = [nom for nom, txt in formats if 'AMBRE' not in txt]
        self.assertFalse(
            muets,
            f"ces formats ne publient pas le statut consolide : {muets}")

    def test_stc_3_la_valeur_publiee_est_DERIVEE_des_agents(self):
        """STC-3 : elle SUIT les statuts, elle n'est pas ecrite.

        ⚠️ Sans ce controle, publier le litteral « AMBRE » passerait STC-1 et
        STC-2. Un agent ROUGE doit faire basculer le paragraphe consolide.
        """
        paras = _paragraphes_docx(
            RE.export_word_equipe(_results_un_agent_rouge()))
        porteurs = [p for p in paras if _LIBELLE_CONSOLIDE in p]
        self.assertTrue(porteurs, "le paragraphe consolide a disparu")
        self.assertTrue(
            any('ROUGE' in p for p in porteurs),
            f"un agent ROUGE ne fait pas basculer le consolide : {porteurs}")
        self.assertFalse(
            any('AMBRE' in p for p in porteurs),
            f"le consolide porte encore AMBRE malgre un agent ROUGE : "
            f"{porteurs}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
