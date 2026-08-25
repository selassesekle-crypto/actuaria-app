"""CONTRÔLES POSITIFS DU LOT ① — la fiche d'aide à la décision d'A6.

Deux constats, et **ils ne peuvent pas être traités séparément** :

  `a6/C11` — la fiche était publiée à **25 %** : 3 champs sur 12. Forces,
             faiblesses, risques, alternatives et questions à poser avant
             signature — le contenu même d'une aide à la décision — n'atteignaient
             AUCUN livrable. Un `isinstance(v, str)` les triait par TYPE.
  `a6/C5`  — la fiche affirmait « Conformité S2 Pilier 1 : modèle validé sur
             données de test indépendantes » **inconditionnellement**, même
             walk-forward échoué et statut plafonné.

⚠️⚠️ LE COUPLAGE EST L'OBJET DU LOT. Corriger `C11` seul — rendre les listes
publiables — **publierait l'affirmation de conformité fausse dans le classeur
qui part au CAC**. La classe `POS_Fiche_LeCouplageEstVerrouille` est là pour
qu'on ne puisse plus les dissocier.

⚠️ ET TOUT SE MESURE PAR EXÉCUTION. Sur ce champ précis, `grep` et la lecture
du code ont donné deux réponses fausses avant que l'exécution ne tranche : on
PRODUIT le classeur et on lit ses cellules.
"""
import io
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import openpyxl

from core.conformite_reglementaire import avertissement_walk_forward
from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
from direction_non_vie.tarification.services.tarif_excel import export_excel_a6

PHRASE_S2 = "modèle validé sur données de test indépendantes"

_MODELE = {'modele': 'GBM', 'famille': 'GBM', 'gini_test': 0.2145,
           'gini_train': 0.23, 'overfit_ratio': 1.07, 'score_global': 0.8373,
           'rmse_test': 12.3}
#: ⚠️ UN BACKTEST RÉELLEMENT CONFORME — les six conditions de
#: `avertissement_walk_forward`, pas une approximation. Ma première version en
#: manquait une (`modele_recalibre_fidele`) et le contrôle POSITIF a échoué :
#: c'est exactement son rôle. On corrige le TÉMOIN, jamais l'assertion.
_BACKTEST_OK = {'disponible': True, 'modele_recalibre_fidele': True,
                'modele_recalibre': 'GBM', 'n_fenetres': 3,
                'gini_wf_moyen': 0.20, 'ae_ratio': 1.00, 'ae_moyen_wf': 1.00,
                'n_fenetres_rouge': 0, 'stabilite_wf': '🟢 stable',
                'methode': 'walk_forward_temporel'}


def _texte_du_classeur(blob: bytes) -> str:
    """Le texte RÉELLEMENT présent dans les cellules produites."""
    wb = openpyxl.load_workbook(io.BytesIO(blob))
    return "\n".join(str(c.value) for ws in wb.worksheets
                     for row in ws.iter_rows() for c in row
                     if c.value is not None)


def _fiche(backtest, statut) -> dict:
    agent = AgentA6Comparaison(audit_path='/tmp', verbose=False)
    return agent._generer_fiche_decision(
        [dict(_MODELE, rang=1)], _MODELE, 'equilibre',
        backtest=backtest, statut_rag=statut)


def _classeur(fiche: dict) -> str:
    res = {'success': True, 'branche': 'auto', 'statut_rag': 'VERT',
           'classement': [dict(_MODELE, rang=1)], 'modele_production': _MODELE,
           'backtest': _BACKTEST_OK, 'fiche_decision': fiche,
           'audit_trail': {}, 'validation_selection': {}}
    return _texte_du_classeur(export_excel_a6(res, audit_id='CTRL'))


class POS_FicheC11_LesDouzeChampsAtteignentLeClasseur(unittest.TestCase):
    """⚠️ `a6/C11` — mesuré AVANT : 3/12 champs publiés (25 %)."""

    def test_aucun_champ_de_la_fiche_n_est_muet(self):
        fiche = _fiche(_BACKTEST_OK, 'VERT')
        self.assertGreaterEqual(len(fiche), 12,
                                f"la fiche ne porte que {len(fiche)} champs")
        txt = _classeur(fiche)
        muets = []
        for cle, val in fiche.items():
            temoins = ([str(x) for x in val] if isinstance(val, (list, tuple))
                       else [str(val)])
            temoins = [t for t in temoins if t.strip()]
            if temoins and not any(t in txt for t in temoins):
                muets.append(cle)
        self.assertEqual(
            muets, [],
            f"{len(muets)} champ(s) de la fiche n'atteignent pas le classeur : "
            f"{muets} — c'est le constat a6/C11 qui revient")
        print(f"    POS-C11 les {len(fiche)} champs de la fiche sont publies ✅")

    def test_une_LISTE_est_rendue_element_par_element(self):
        """⚠️ LE SECOND SENS : écrire `str(la_liste)` publierait
        `['a', 'b']` — techniquement « publié », illisible pour l'actuaire."""
        fiche = _fiche(_BACKTEST_OK, 'VERT')
        listes = {k: v for k, v in fiche.items() if isinstance(v, (list, tuple)) and v}
        self.assertTrue(listes, "la fiche ne porte aucune liste")
        txt = _classeur(fiche)
        for cle, val in listes.items():
            with self.subTest(champ=cle):
                self.assertNotIn(str(val), txt,
                                 f"{cle} est publie comme repr Python")
                self.assertIn(str(val[0]), txt,
                              f"{cle} : le premier element est absent")
        print(f"    POS-C11 les {len(listes)} listes sont rendues ligne a ligne ✅")


class POS_FicheC5_LaConformiteS2EstConditionnelle(unittest.TestCase):
    """⚠️ `a6/C5` — la phrase était écrite TOUJOURS."""

    def test_walk_forward_reussi_et_statut_VERT_alors_la_phrase_EST_ecrite(self):
        """⚠️⚠️ LE SECOND SENS, ET IL EST PREMIER ICI : une garde qui
        refuserait TOUT passerait les tests négatifs sans rien prouver. Le
        module doit encore pouvoir attester quand il en a le droit."""
        self.assertIsNone(avertissement_walk_forward(_BACKTEST_OK),
                          "le backtest temoin n'est pas juge conforme")
        justif = " ".join(_fiche(_BACKTEST_OK, 'VERT')['justification_regl'])
        self.assertIn(PHRASE_S2, justif)
        self.assertNotIn("NON ÉTABLIE", justif)
        print("    POS-C5 walk-forward OK + VERT -> la conformite EST attestee ✅")

    def test_walk_forward_indisponible_alors_la_phrase_est_RETIREE(self):
        justif = " ".join(_fiche(None, 'VERT')['justification_regl'])
        self.assertNotIn(PHRASE_S2, justif,
                         "la conformite S2 est affirmee sans validation temporelle")
        self.assertIn("NON ÉTABLIE", justif)
        print("    POS-C5 aucun walk-forward -> conformite NON ETABLIE ✅")

    def test_statut_plafonne_alors_la_phrase_est_RETIREE(self):
        for statut in ('AMBRE', 'ROUGE'):
            with self.subTest(statut=statut):
                justif = " ".join(_fiche(_BACKTEST_OK, statut)['justification_regl'])
                self.assertNotIn(PHRASE_S2, justif,
                                 f"conformite S2 affirmee sur un modele {statut}")
                self.assertIn(statut, justif,
                              "le motif ne nomme pas le statut qui bloque")
        print("    POS-C5 statut plafonne -> conformite NON ETABLIE ✅")

    def test_l_absence_d_attestation_n_est_JAMAIS_silencieuse(self):
        """⚠️ On ne retire pas la ligne : on écrit qu'elle n'est pas établie.
        Une ligne manquante se lit comme un oubli."""
        justif = _fiche(None, 'AMBRE')['justification_regl']
        self.assertTrue(justif, "la justification reglementaire est VIDE")
        self.assertTrue(any('NON ÉTABLIE' in x for x in justif))
        print("    POS-C5 l'absence d'attestation se DENONCE ✅")


class POS_Fiche_LeCouplageEstVerrouille(unittest.TestCase):
    """⚠️⚠️ LE CONTRÔLE QUI EMPÊCHE DE DISSOCIER LES DEUX CORRECTIFS.

    `C11` rend la fiche publiable ; `C5` rend son attestation conditionnelle.
    **Publier sans conditionner mettrait une conformité S2 fausse dans le
    classeur qui part au CAC.** Ce test lit le CLASSEUR, pas la fiche : il
    échouerait aussi bien si l'on revenait sur `C5` que si l'on publiait la
    fiche par un autre chemin.
    """

    def test_le_classeur_ne_porte_JAMAIS_la_phrase_quand_elle_est_fausse(self):
        for libelle, bt, statut in (
            ('aucun walk-forward', None, 'VERT'),
            ('walk-forward indisponible', {'disponible': False}, 'VERT'),
            ('statut AMBRE', _BACKTEST_OK, 'AMBRE'),
            ('statut ROUGE', _BACKTEST_OK, 'ROUGE'),
        ):
            with self.subTest(cas=libelle):
                txt = _classeur(_fiche(bt, statut))
                self.assertNotIn(
                    PHRASE_S2, txt,
                    f"[{libelle}] le CLASSEUR affirme la conformite S2 alors "
                    f"qu'elle n'est pas etablie — c'est le BLOQUANT B3 sous "
                    f"une autre forme")
        print("    POS-couplage le classeur ne publie jamais une S2 fausse ✅")

    def test_backtest_et_statut_ne_peuvent_PAS_etre_omis(self):
        """⚠️ Un défaut à None rouvrirait la porte en silence — même doctrine
        que le `X_val` rendu obligatoire dans A5 au lot 1.1."""
        agent = AgentA6Comparaison(audit_path='/tmp', verbose=False)
        with self.assertRaises(TypeError):
            agent._generer_fiche_decision([dict(_MODELE, rang=1)], _MODELE,
                                          'equilibre')
        print("    POS-couplage backtest et statut sont EXIGES ✅")

    def test_le_classeur_produit_est_un_vrai_xlsx(self):
        """Garde-fou du banc lui-même : si l'export échouait en silence, tous
        les tests ci-dessus passeraient sur une chaîne vide."""
        res = {'success': True, 'branche': 'auto', 'statut_rag': 'VERT',
               'classement': [dict(_MODELE, rang=1)],
               'modele_production': _MODELE, 'backtest': _BACKTEST_OK,
               'fiche_decision': _fiche(_BACKTEST_OK, 'VERT'),
               'audit_trail': {}, 'validation_selection': {}}
        blob = export_excel_a6(res, audit_id='CTRL')
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(blob)),
                        "l'export ne produit pas une archive xlsx")
        self.assertGreater(len(_texte_du_classeur(blob)), 200,
                           "le classeur produit est quasi vide")
        print("    POS-couplage le banc produit un vrai classeur ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
