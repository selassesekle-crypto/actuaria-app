"""CONTRÔLES POSITIFS DU LOT ② — `conformite/C1` + `conformite/C7`.

  `C1` — `controle_effet_execute` valait `True` alors que le contrôle n'avait
         examiné AUCUNE colonne. Il était calculé AVANT l'appel, sur la seule
         présence des arguments : `not (df is None or not cibles)`.
         `detecter_fuites_par_effet` renonçait en silence dans deux cas —
         cible absente du DataFrame, cible de variance nulle.
         **La propriété attestait la FOURNITURE DES ARGUMENTS, pas
         l'EXÉCUTION DU CONTRÔLE.**
  `C7` — cette même propriété portait « ⚠ À REMONTER DANS LES RAPPORTS »
         depuis l'audit V14. Mesuré : **aucun agent, aucun service, aucun
         livrable ne la lisait.**

⚠️⚠️ LE COUPLAGE EST L'OBJET DU LOT, ET IL EST ORIENTÉ.
Publier `C7` sans corriger `C1` aurait mis dans le livrable une attestation
**fausse** : « garde-fou n°4 exécuté » sur une matrice où il n'avait examiné
aucune colonne. `C1` est donc corrigé D'ABORD, dans le même changement.
`POS_Effet_LeCouplageEstVerrouille` lit le CLASSEUR PRODUIT — elle échoue si
l'on revient sur `C1`, comme si l'on débranchait `C7`.

⚠️ Tout se conclut PAR EXÉCUTION : on produit le classeur et on lit ses cellules.
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import numpy as np
import openpyxl
import pandas as pd

import core.conformite_reglementaire as C
from direction_non_vie.tarification.services.tarif_excel import export_excel_a6

_FEATURES = ['age', 'bonus_malus']


def _donnees(n=300, cible='variable'):
    rng = np.random.default_rng(1)
    df = pd.DataFrame({'age': rng.uniform(20, 70, n),
                       'bonus_malus': rng.uniform(50, 200, n)})
    if cible == 'variable':
        df['nb'] = rng.poisson(0.3, n).astype(float)
    elif cible == 'constante':
        df['nb'] = np.zeros(n)
    return df


def _matrice(df, col_cible='nb', contexte='ctrl'):
    return C.construire_matrice_x(_FEATURES, contexte=contexte, df=df,
                                  col_cible=col_cible)


def _rapport(mx) -> dict:
    return {'execute': mx.controle_effet_execute,
            'motifs': mx.motifs_controle_effet}


def _classeur(controle_effet: dict) -> str:
    modele = {'modele': 'GBM', 'famille': 'GBM', 'gini_test': 0.21,
              'overfit_ratio': 1.07, 'score_global': 0.83, 'rmse_test': 12.3}
    res = {'success': True, 'branche': 'auto', 'statut_rag': 'VERT',
           'classement': [dict(modele, rang=1)], 'modele_production': modele,
           'backtest': {'disponible': True}, 'fiche_decision': {},
           'audit_trail': {}, 'validation_selection': {},
           'controle_effet': controle_effet}
    wb = openpyxl.load_workbook(io.BytesIO(export_excel_a6(res, audit_id='CTRL')))
    return "\n".join(str(c.value) for ws in wb.worksheets
                     for row in ws.iter_rows() for c in row
                     if c.value is not None)


class POS_Effet_C1_LaProprieteAtteste_L_EXECUTION(unittest.TestCase):
    """⚠️ `conformite/C1` — elle attestait la fourniture des arguments."""

    def test_les_trois_cas_muets_ne_sont_plus_attestes(self):
        cas = {
            'cible ABSENTE du df': (_donnees(cible='absente'), 'nb'),
            'cible CONSTANTE': (_donnees(cible='constante'), 'nb'),
            'df absent': (None, 'nb'),
        }
        for libelle, (df, cible) in cas.items():
            with self.subTest(cas=libelle):
                mx = _matrice(df, cible, libelle)
                self.assertFalse(
                    mx.controle_effet_execute,
                    f"[{libelle}] la matrice atteste un controle qui n'a "
                    f"examine AUCUNE colonne")
                self.assertTrue(
                    mx.motifs_controle_effet,
                    f"[{libelle}] aucun motif : l'actuaire saurait QUE, "
                    f"jamais POURQUOI")
        print(f"    POS-C1 les {len(cas)} cas muets ne sont plus attestes ✅")

    def test_LE_SECOND_SENS_un_controle_qui_TOURNE_est_bien_atteste(self):
        """⚠️⚠️ SANS LUI, UNE PROPRIÉTÉ FIGÉE À `False` PASSERAIT LES TROIS
        TESTS CI-DESSUS. Le garde-fou doit encore pouvoir dire qu'il a tourné."""
        mx = _matrice(_donnees(), 'nb')
        self.assertTrue(mx.controle_effet_execute,
                        "un controle qui a tourne se declare non execute")
        self.assertEqual(mx.motifs_controle_effet, {},
                         "un controle complet ne doit porter aucun motif")
        print("    POS-C1 LE SECOND SENS : un controle qui tourne est atteste ✅")

    def test_le_motif_NOMME_la_cause(self):
        """Un booléen dit QUE ; l'actuaire a besoin de POURQUOI."""
        for cible, mot in (('absente', 'ABSENTE'), ('constante', 'CONSTANTE')):
            with self.subTest(cas=cible):
                mx = _matrice(_donnees(cible=cible), 'nb')
                motifs = " ".join(mx.motifs_controle_effet.values())
                self.assertIn(mot, motifs)
        print("    POS-C1 le motif nomme la cause ✅")

    def test_le_WARNING_ne_se_contredit_PAS_lui_meme(self):
        """⚠️ Mon premier correctif annonçait « appelée SANS df et/ou SANS
        col_cible » alors que les DEUX étaient fournis — l'en-tête contredisait
        le motif qu'il portait. Le défaut de ce module, dans son correctif."""
        import logging as _lg
        journal = []

        class _Espion(_lg.Handler):
            def emit(self, record):
                journal.append(record.getMessage())

        log = _lg.getLogger('ctrl_effet_espion')
        log.setLevel(_lg.WARNING)
        log.addHandler(_Espion())
        try:
            _matrice(_donnees(cible='absente'), 'nb')
            C.construire_matrice_x(_FEATURES, contexte='espion',
                                   df=_donnees(cible='absente'),
                                   col_cible='nb', logger_agent=log)
        finally:
            log.handlers.clear()
        msg = " ".join(journal)
        self.assertIn("aucune cible exploitable", msg,
                      "le WARNING n'annonce pas la vraie cause")
        self.assertNotIn("SANS df et/ou SANS col_cible", msg,
                         "le WARNING affirme une cause FAUSSE : df et "
                         "col_cible ont bien ete fournis")
        print("    POS-C1 le WARNING annonce la vraie cause ✅")

    def test_une_cible_sur_deux_est_un_controle_PARTIEL_declare(self):
        """⚠️ L'agrégation ne doit pas arrondir au meilleur : A3 passe DEUX
        cibles, et l'une peut manquer."""
        mx = C.construire_matrice_x(_FEATURES, contexte='partiel',
                                    df=_donnees(), col_cible=['nb', 'absente'])
        self.assertTrue(mx.controle_effet_execute, "une cible valide suffit")
        self.assertIn('absente', mx.motifs_controle_effet,
                      "la cible non examinee n'est pas signalee")
        avert = C.avertissement_controle_effet(_rapport(mx))
        self.assertIsNotNone(avert)
        self.assertIn('PARTIEL', avert)
        print("    POS-C1 couverture partielle : declaree, pas arrondie ✅")


class POS_Effet_C7_LAvertissementATTEINTLeLivrable(unittest.TestCase):
    """⚠️ `conformite/C7` — la propriété n'atteignait aucun livrable."""

    def test_le_classeur_porte_l_avertissement_quand_le_controle_n_a_pas_tourne(self):
        txt = _classeur(_rapport(_matrice(None, 'nb')))
        self.assertIn("NON EXÉCUTÉ", txt,
                      "le classeur ne dit pas que le garde-fou n'a pas tourne")
        self.assertIn("aucun DataFrame", txt,
                      "le classeur ne publie pas le MOTIF")
        print("    POS-C7 le classeur porte l'avertissement ET son motif ✅")

    def test_LE_SECOND_SENS_rien_n_est_publie_quand_tout_va_bien(self):
        """⚠️ Un avertissement affiché en permanence ne serait plus un
        avertissement : l'actuaire cesserait de le lire."""
        txt = _classeur(_rapport(_matrice(_donnees(), 'nb')))
        self.assertNotIn("NON EXÉCUTÉ", txt)
        self.assertIn("exécuté sur toutes les cibles", txt,
                      "l'etat SAIN n'est pas publie non plus — l'actuaire ne "
                      "peut pas distinguer « tout va bien » de « rien n'a ete "
                      "verifie »")
        print("    POS-C7 LE SECOND SENS : etat sain publie, pas d'alarme ✅")


class POS_Effet_LeCouplageEstVerrouille(unittest.TestCase):
    """⚠️⚠️ `C7` NE PEUT PAS ÊTRE PUBLIÉ SI `C1` N'EST PAS VRAI.

    Ce test lit le CLASSEUR PRODUIT, pas la propriété : il échoue si l'on
    revient sur `C1` (la propriété redeviendrait `True` à tort et le classeur
    attesterait un contrôle jamais exécuté), comme si l'on débranchait `C7`.
    """

    def test_le_classeur_n_atteste_JAMAIS_un_controle_qui_n_a_rien_examine(self):
        for libelle, df, cible in (
            ('df absent', None, 'nb'),
            ('cible absente', _donnees(cible='absente'), 'nb'),
            ('cible constante', _donnees(cible='constante'), 'nb'),
        ):
            with self.subTest(cas=libelle):
                txt = _classeur(_rapport(_matrice(df, cible, libelle)))
                self.assertNotIn(
                    "exécuté sur toutes les cibles", txt,
                    f"[{libelle}] LE CLASSEUR ATTESTE un controle anti-fuite "
                    f"qui n'a examine AUCUNE colonne — c'est le constat C1 "
                    f"publie, donc pire qu'avant")
        print("    POS-couplage le classeur n'atteste jamais a tort ✅")

    def test_la_source_unique_est_la_MEME_pour_les_deux_sorties_muettes(self):
        """⚠️ `detecter_fuites_par_effet` et `construire_matrice_x` doivent
        consulter LA MÊME fonction. Deux tests séparés se désynchroniseraient —
        c'est la maladie que ce module existe pour supprimer."""
        for cible in ('absente', 'constante'):
            with self.subTest(cas=cible):
                df = _donnees(cible=cible)
                self.assertIsNotNone(
                    C.motif_controle_effet_impossible(df, 'nb'),
                    "la source unique ne voit pas ce cas")
                self.assertEqual(
                    C.detecter_fuites_par_effet(df, _FEATURES, 'nb'), {},
                    "la detection ne renonce pas sur ce cas")
                self.assertFalse(_matrice(df, 'nb').controle_effet_execute,
                                 "la matrice atteste malgre le renoncement")
        print("    POS-couplage une seule source pour les deux sorties ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
