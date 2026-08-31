# -*- coding: utf-8 -*-
"""CONTRÔLES POSITIFS — services/C1 : l'horodatage du livrable de tarification.

Le défaut mesuré : « Arrêté : » portait la date de GÉNÉRATION (avec une heure,
ex. « 23/08/2026 14:38 »), et l'absence d'arrêté était masquée par la date du
jour glissée sous cette étiquette. Après correctif (troisième voie arbitrée) :

  · « Arrêté »   = date de RÉFÉRENCE déclarée, dérivée de `core/arrete.py` ;
  · absente      → « non déclaré », VISIBLE, jamais un now() ni une heure ;
  · « Généré le » = date d'impression, sur TOUT document (arrêté ou non) ;
  · le CONTENU (empreinte + primes) rejoue à l'identique — seule la date de
    génération varie. Reproductibilité du CONTENU, distincte de l'intégrité du
    document (l'archive vérifiable A7, chantier séparé, non traité ici).

⚠️ TOUT SE MESURE PAR EXÉCUTION : on PRODUIT le classeur / on tarife, et on lit.
"""
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import openpyxl

from direction_non_vie.tarification.services.entete_livrable import (
    libelle_arrete, genere_le, ARRETE_NON_DECLARE)
from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
from direction_non_vie.tarification.services.tarif_excel import export_excel_a6

_MODELE = {'modele': 'GBM', 'famille': 'GBM', 'gini_test': 0.2145,
           'gini_train': 0.23, 'overfit_ratio': 1.07, 'score_global': 0.8373,
           'rmse_test': 12.3}
_BACKTEST_OK = {'disponible': True, 'modele_recalibre_fidele': True,
                'modele_recalibre': 'GBM', 'n_fenetres': 3, 'gini_wf_moyen': 0.20,
                'ae_ratio': 1.00, 'ae_moyen_wf': 1.00, 'n_fenetres_rouge': 0,
                'stabilite_wf': '🟢 stable', 'methode': 'walk_forward_temporel'}


def _res_a6() -> dict:
    """Un résultat A6 minimal mais VALIDE — même patron que test_fiche_decision."""
    agent = AgentA6Comparaison(audit_path=tempfile.mkdtemp(), verbose=False)
    fiche = agent._generer_fiche_decision(
        [dict(_MODELE, rang=1)], _MODELE, 'equilibre',
        backtest=_BACKTEST_OK, statut_rag='VERT')
    return {'success': True, 'branche': 'auto', 'statut_rag': 'VERT',
            'classement': [dict(_MODELE, rang=1)], 'modele_production': _MODELE,
            'backtest': _BACKTEST_OK, 'fiche_decision': fiche,
            'audit_trail': {}, 'validation_selection': {}}


def _texte(blob: bytes) -> str:
    wb = openpyxl.load_workbook(io.BytesIO(blob))
    return "\n".join(str(c.value) for ws in wb.worksheets
                     for row in ws.iter_rows() for c in row if c.value is not None)


class TestEnteteLivrableHelper(unittest.TestCase):
    """La SOURCE UNIQUE — l'absence est VISIBLE, jamais un now() masquant."""

    def test_absent_est_non_declare(self):
        self.assertEqual(libelle_arrete(None), ARRETE_NON_DECLARE)
        self.assertEqual(libelle_arrete(''), ARRETE_NON_DECLARE)
        self.assertEqual(libelle_arrete('   '), ARRETE_NON_DECLARE)

    def test_declare_derive_le_libelle(self):
        self.assertEqual(libelle_arrete('30/06/2026'), 'T2 2026')    # fin de trimestre
        self.assertEqual(libelle_arrete('2026-06-30'), 'T2 2026')    # autre format, même date
        self.assertEqual(libelle_arrete('15/03/2026'), '15/03/2026')  # hors trimestre

    def test_illisible_reste_visible_jamais_bloquant(self):
        # « Q2 2026 » : un libellé libre, refusé par core/arrete. On ne bloque
        # pas la génération — on rend l'illisibilité VISIBLE.
        lib = libelle_arrete('Q2 2026')
        self.assertIn(ARRETE_NON_DECLARE, lib)

    def test_genere_le_porte_une_heure(self):
        # « Généré le » est une date d'impression : elle porte l'heure.
        self.assertRegex(genere_le(), r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}')


class TestArreteDansLeClasseur(unittest.TestCase):
    """PAR EXÉCUTION : on produit le classeur A6 et on lit ses cellules."""

    def test_absent_affiche_non_declare_jamais_une_heure(self):
        txt = _texte(export_excel_a6(_res_a6(), audit_id='CTRL'))   # aucun arrêté
        self.assertIn(f"Arrêté : {ARRETE_NON_DECLARE}", txt)
        # ⚠️ LE DÉFAUT ORIGINEL : « Arrêté : 23/08/2026 14:38 ». Plus AUCUNE
        # étiquette « Arrêté : » ne doit être suivie d'un horodatage à l'heure.
        self.assertNotRegex(txt, r'Arrêté\s*:\s*\d{2}/\d{2}/\d{4} \d{2}:\d{2}')

    def test_declare_affiche_le_libelle(self):
        txt = _texte(export_excel_a6(_res_a6(), audit_id='CTRL', arrete='30/06/2026'))
        self.assertIn("Arrêté : T2 2026", txt)
        self.assertNotIn(ARRETE_NON_DECLARE, txt)

    def test_genere_le_present_avec_et_sans_arrete(self):
        # ⚠️ « Généré le » sur TOUT document — sans elle, on perd quand ce
        # document précis a été produit.
        for arr in (None, '30/06/2026'):
            txt = _texte(export_excel_a6(_res_a6(), audit_id='CTRL', arrete=arr))
            self.assertIn("Généré le :", txt,
                          f"« Généré le » absent (arrete={arr!r})")


class TestSceauReproductibiliteContenu(unittest.TestCase):
    """④ Mêmes entrées → MÊME empreinte, MÊMES primes ; seule la génération varie.

    Deux exécutions COMPLÈTES (deux ajustements sur des données de même graine).
    Le contenu signé rejoue à l'identique ; `date_calcul` (la génération) varie.
    """

    def test_contenu_rejoue_generation_varie(self):
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        from direction_non_vie.tarification.test_plan_invariants import (
            portefeuille_auto, AUTO)
        contrat = {'age': 40, 'bonus_malus': 0.9, 'anciennete_permis': 20,
                   'puissance_fiscale': 6, 'age_vehicule': 5, 'valeur_venale': 12000,
                   'garantie': 'TousRisques', 'carburant': 'Diesel', 'csp': 'Cadre',
                   'usage': 'Prive', 'antecedents_sinistres_n1': 0,
                   'kilometrage_annuel': 12000, 'milieu_geographique': 'Urbain'}
        t1 = pipeline_complet(portefeuille_auto(n=3000, seed=7), AUTO)
        t2 = pipeline_complet(portefeuille_auto(n=3000, seed=7), AUTO)
        r1 = t1.tarifer(contrat)
        r2 = t2.tarifer(contrat)
        # CONTENU : rejoue à l'identique
        self.assertEqual(r1['plan_empreinte'], r2['plan_empreinte'])
        self.assertEqual(r1['prime_pure'], r2['prime_pure'])
        self.assertEqual(r1['prime_ttc'], r2['prime_ttc'])
        # et l'empreinte porte le schéma versionné (chantier S3, `2cb43ef`)
        # ⚠️⚠️ DÉRIVÉ DE LA CONSTANTE, PLUS ÉCRIT EN DUR (31/08/2026). Ce test
        # épinglait `'s1:'` en littéral, dans un fichier que le sceau du golden
        # (`test_plan_invariants`) ne nomme nulle part : le bump `s1` -> `s2` de
        # l'étape `unite_exposition` l'a fait rougir sans que rien n'ait prévenu
        # qu'il faudrait le toucher. *Une copie en dur de la constante même que
        # le sceau existe pour protéger.*
        from core.plan_tarifaire import EMPREINTE_SCHEMA
        self.assertTrue(r1['plan_empreinte'].startswith(f's{EMPREINTE_SCHEMA}:'))
        # GÉNÉRATION : varie — c'est une métadonnée, exclue du contenu
        self.assertNotEqual(r1['date_calcul'], r2['date_calcul'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
