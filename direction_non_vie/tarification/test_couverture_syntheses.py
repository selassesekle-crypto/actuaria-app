# -*- coding: utf-8 -*-
"""
=============================================================================
  COUVERTURE COMPLETE : chaque synthese atteint chaque livrable signe
=============================================================================

DEUX RENDUS A LA MAIN PRENAIENT DU RETARD, ET RIEN NE LE DISAIT.

  L'EXCEL D'EQUIPE ne parcourt pas `_LABELS_SYNTHESES` : il code UN BLOC PAR
  CLE. Mesure du 03/09/2026 : **13 cles sur 16**. Manquaient `plan_ecarte`
  (`conformite/C15`), `exempt_effet` (`conformite/C4`) et `plafond`
  (`services/C7`) -- ce dernier le plus genant, son constat existant
  precisement pour qu'une cause de statut atteigne TOUS les livrables.

  LE RAPPORT MODELES ne portait aucune des trois reserves d'A6. Elles
  n'atteignaient donc qu'**une surface sur six**, l'Excel A6.

  *Un rendu par enumeration et un rendu a la main ne se maintiennent pas au
  meme rythme : c'est le second qui prend du retard, et il faut un filet
  SOUS lui, pas a sa place.*

-----------------------------------------------------------------------------
POURQUOI L'EXCEL N'A PAS ETE REECRIT EN BOUCLE
-----------------------------------------------------------------------------
Chaque synthese y a SA place (le walk-forward dans la section BACKTESTING,
la validation DL dans GOUVERNANCE), SON libelle -- avec des prefixes
<< ⚠ >> / << ℹ >> que `_LABELS_SYNTHESES` ne porte pas -- et SA regle de
badge (<< AMBRE si ACTION REQUISE >>, etc.). Une boucle unique aurait
detruit les trois, sur un livrable signe.

Le geste retenu : **lire une cle vaut l'enregistrer**, et ce qu'aucun bloc
n'a pris est rendu en fin de section. Un bloc supprime emporte son
enregistrement, donc sa cle retombe dans le filet -- le mecanisme se repare
tout seul.

-----------------------------------------------------------------------------
LES SIX SURFACES SIGNEES
-----------------------------------------------------------------------------
    equipe.html · equipe.word · equipe.excel
    modeles.html · modeles.word · a6.excel

⚠️ Elles s'enumerent ICI, une fois pour toutes. J'ai deja conclu << aucune
surface >> sur un releve fait a DEUX services sur trois : *un releve partiel
conclut faux, et toujours vers l'alarme.*
=============================================================================
"""

import io
import unittest
import zipfile

from direction_non_vie.tarification.services import (
    rapport_equipe_tarif as RE,
)
from direction_non_vie.tarification.services import (
    rapport_modeles_tarif as RM,
)
from direction_non_vie.tarification.services import (
    tarif_excel as TX,
)


def _docx(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return z.read('word/document.xml').decode('utf-8')


def _xlsx(blob: bytes) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(blob))
    return '\n'.join(str(c.value) for ws in wb.worksheets
                     for row in ws.iter_rows() for c in row
                     if c.value is not None)


def _r6(**extra):
    base = {'success': True, 'statut_rag': 'AMBRE', 'branche': 'auto',
            'modele_production': {'modele': 'GLM'}, 'backtest': {},
            'audit_trail': {}, 'classement': [], 'metriques': {}}
    base.update(extra)
    return base


class T1_LExcelDEquipeRendTOUTES_les_cles(unittest.TestCase):

    def test_cs_1_les_seize_cles_atteignent_les_TROIS_formats_d_equipe(self):
        """CS-1 : plus AUCUNE clé absente d'un format.

        ⚠️ Aucune liste de trous n'est declaree ici, et c'est le point : le
        filet de fin de section les couvre TOUTES. Une exemption serait le
        retour du defaut.
        """
        for cle, _ in RE._LABELS_SYNTHESES:
            temoin = f'ZZ{cle.upper().replace("_", "")}ZZ'
            res, synth = {'a6': _r6()}, {cle: temoin}
            sorties = {
                'html': RE.export_html_equipe(res, syntheses=synth),
                'word': _docx(RE.export_word_equipe(res, syntheses=synth)),
                'excel': _xlsx(RE.export_excel_equipe(res, syntheses=synth)),
            }
            for nom, texte in sorties.items():
                with self.subTest(cle=cle, format=nom):
                    self.assertIn(
                        temoin, texte,
                        f"« {cle} » n'atteint pas {nom}. Si c'est une cle "
                        f"nouvelle, le filet de fin de section aurait du la "
                        f"prendre : verifier qu'elle a bien un LIBELLE dans "
                        f"`_LABELS_SYNTHESES`.")

    def test_cs_2_une_cle_INCONNUE_des_blocs_est_rendue_par_le_FILET(self):
        """CS-2 : le mecanisme lui-meme, pas seulement son resultat.

        ⚠️ Sans ce controle, quelqu'un pourrait recabler les trois cles a la
        main et supprimer le filet : `CS-1` resterait vert, et la PROCHAINE
        cle retomberait dans le trou. *Ce qui doit tenir, c'est le
        mecanisme, pas l'etat qu'il produit aujourd'hui.*
        """
        libelles = dict(RE._LABELS_SYNTHESES)
        # une cle qui n'a AUCUN bloc dedie dans l'Excel
        cle = 'exempt_effet'
        self.assertIn(cle, libelles)
        temoin = 'ZZFILETZZ'
        texte = _xlsx(RE.export_excel_equipe(
            {'a6': _r6()}, syntheses={cle: temoin}))
        self.assertIn(temoin, texte)
        self.assertIn(
            'AUTRES SYNTHÈSES RÉGLEMENTAIRES', texte,
            "la cle est rendue mais PAS par le filet : verifier qu'un bloc "
            "a la main ne l'a pas reprise, auquel cas le filet n'est plus "
            "eprouve par ce controle")

    def test_cs_3_rien_n_est_rendu_quand_il_n_y_a_rien_a_dire(self):
        """CS-3 : le second sens. Un filet qui affiche toujours est du bruit.

        ⚠️ MA PREMIERE FIXTURE ETAIT FAUSSE, et l'echec l'a montre : sur un
        `result_a6` minimal, le statut est AMBRE et `synthese_raisons_plafond`
        a donc bien quelque chose a dire -- le filet le rendait a bon droit.
        *Un << rien a dire >> se construit, il ne se suppose pas.* Il faut un
        statut VERT, ou cette synthese rend `None`.
        """
        texte = _xlsx(RE.export_excel_equipe(
            {'a6': _r6(statut_rag='VERT')}))
        self.assertNotIn('AUTRES SYNTHÈSES RÉGLEMENTAIRES', texte)


class T2_LeRapportModelesPorteLesReserves(unittest.TestCase):

    def test_cs_4_les_trois_reserves_atteignent_html_ET_word(self):
        """CS-4 : les deux formats, jamais un seul.

        ⚠️ Corriger un seul des deux laisserait la moitie du livrable signe
        muette -- c'est exactement ce qui s'etait produit pour
        l'avertissement DL (`avertissement_dl`).
        """
        for cle, _ in RM.RESERVES_A6:
            temoin = f'ZZ{cle.upper().replace("_", "")}ZZ'
            r6 = _r6(**{cle: temoin})
            with self.subTest(cle=cle, format='html'):
                self.assertIn(temoin, RM.export_html({}, {}, r6))
            with self.subTest(cle=cle, format='word'):
                self.assertIn(temoin, _docx(RM.export_word({}, {}, r6)))

    def test_cs_5_l_ordre_est_STABLE_et_rien_si_rien(self):
        """CS-5 : deux executions rendent le meme document.

        ⚠️ L'ordre vient de `RESERVES_A6`, pas du dictionnaire.
        """
        r6 = _r6(reserve_bases_gini='C', reserve_arbitrage='A',
                 reserve_vraisemblance='B')
        rendues = [lib for lib, _ in RM.reserves_arbitrage(r6)]
        self.assertEqual(rendues, [lib for _, lib in RM.RESERVES_A6])
        self.assertEqual(RM.reserves_arbitrage(_r6()), ())
        self.assertEqual(RM.reserves_arbitrage(None), ())
        self.assertEqual(RM.reserves_arbitrage(_r6(reserve_arbitrage='   ')),
                         ())


class T3_LesSixSurfaces(unittest.TestCase):
    """⚠️ L'ASSIETTE COMPLETE, enumeree une fois pour toutes."""

    def test_cs_6_les_reserves_atteignent_les_SIX_surfaces(self):
        """CS-6 : de 1/6 a 6/6, mesure de bout en bout."""
        for cle, _ in RM.RESERVES_A6:
            temoin = f'ZZ{cle.upper().replace("_", "")}ZZ'
            r6 = _r6(**{cle: temoin})
            res = {'a6': r6}
            surfaces = {
                'equipe.html': RE.export_html_equipe(res),
                'equipe.word': _docx(RE.export_word_equipe(res)),
                'equipe.excel': _xlsx(RE.export_excel_equipe(res)),
                'modeles.html': RM.export_html({}, {}, r6),
                'modeles.word': _docx(RM.export_word({}, {}, r6)),
                'a6.excel': _xlsx(TX.export_excel_a6(r6)),
            }
            manquantes = [nom for nom, txt in surfaces.items()
                          if temoin not in txt]
            with self.subTest(cle=cle):
                self.assertFalse(
                    manquantes,
                    f"« {cle} » n'atteint pas {manquantes} sur les six "
                    f"surfaces signees")


if __name__ == '__main__':
    unittest.main(verbosity=2)
