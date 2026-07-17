"""
Fondation B1 (Phase 5) — core/derivations.py + PlanTarifaire.colonnes_attendues().

La relation dérivée→source est désormais dans core (SOURCE UNIQUE), partagée par
A2 (message de valider_contre), le plan (colonnes_attendues) et le futur moteur de
mapping. Ce fichier verrouille :
  · cohérence DERIVATIONS ↔ DATA_DICTIONNAIRE (sur les 3 dérivées documentées) ;
  · cohérence DERIVATIONS ↔ COMPORTEMENT RÉEL d'A2._calculer_indicateurs_derives
    (la vraie vérité : le code) ;
  · colonnes_attendues() = entrée BRUTE (kilometrage_annuel, pas km_par_an_normalise) ;
  · le correctif #4 (valider_contre) désormais COMPLET pour mrh (valeur_mobilier).
"""
import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from core.derivations import DERIVATIONS, sources_brutes
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing, DATA_DICTIONNAIRE)
from direction_non_vie.tarification.test_plan_invariants import (
    AUTO, MRH, RCPRO, portefeuille_mrh, _a2)


def _norm(src):
    return (src,) if isinstance(src, str) else tuple(src)


class TestDerivations(unittest.TestCase):

    def test_coherence_data_dictionnaire(self):
        """Sur les dérivées communes aux deux tables, les sources concordent —
        garde-fou anti-dérive. DATA_DICTIONNAIRE n'en documente que 3 (auto) ; la
        table core est délibérément complète (9)."""
        communes = set(DERIVATIONS) & set(DATA_DICTIONNAIRE)
        self.assertEqual(communes,
                         {'risque_historique', 'km_par_an_normalise', 'jeune_conducteur'},
                         "les dérivées documentées par DATA_DICTIONNAIRE ont changé")
        for k in communes:
            self.assertEqual(DERIVATIONS[k], _norm(DATA_DICTIONNAIRE[k]['source']),
                             f"source divergente pour '{k}'")
        print(f"    B1 cohérence DERIVATIONS↔DATA_DICTIONNAIRE : {sorted(communes)} ✅")

    def test_coherence_comportement_a2(self):
        """DERIVATIONS reflète le COMPORTEMENT RÉEL d'A2 : avec toutes les sources
        brutes, les 9 dérivées sont produites ; retirer une source brute supprime
        la dérivée qui en dépend (garde par présence des sources dans le code)."""
        base = pd.DataFrame({
            'bonus_malus': [1.0] * 5, 'antecedents_sinistres_n1': [0.0] * 5,
            'kilometrage_annuel': [10000.0] * 5, 'exposition': [1.0] * 5,
            'age': [40.0] * 5, 'age_vehicule': [5.0] * 5,
            'valeur_mobilier': [30000.0] * 5, 'surface_m2': [70.0] * 5,
            'annee_construction': [1990.0] * 5,
        })
        a2 = AgentA2Preprocessing(models_path='/tmp', audit_path='/tmp', verbose=False)
        out = a2._calculer_indicateurs_derives(base.copy())
        for d in DERIVATIONS:
            self.assertIn(d, out.columns, f"A2 ne produit pas la dérivée déclarée '{d}'")

        # retrait ciblé → la/les dérivée(s) dépendante(s) disparaît/-ssent
        for source_retiree, derivees in [
            ('kilometrage_annuel', ['km_par_an_normalise']),
            ('valeur_mobilier',    ['valeur_par_m2']),
            ('annee_construction', ['age_logement', 'logement_ancien']),  # récursif
        ]:
            out2 = a2._calculer_indicateurs_derives(base.drop(columns=[source_retiree]).copy())
            for d in derivees:
                self.assertNotIn(d, out2.columns,
                    f"'{d}' produite alors que sa source '{source_retiree}' est absente")
        print("    B1 cohérence DERIVATIONS↔comportement A2 : 9 dérivées + gardes ✅")

    def test_colonnes_attendues_resout_les_derivees(self):
        """colonnes_attendues() renvoie la SOURCE BRUTE, jamais la dérivée."""
        att_auto = set(AUTO.colonnes_attendues())
        self.assertIn('kilometrage_annuel', att_auto)
        self.assertNotIn('km_par_an_normalise', att_auto)
        self.assertTrue({'exposition', 'nb_sinistres', 'cout_total_sinistres'} <= att_auto)

        att_mrh = set(MRH.colonnes_attendues())
        self.assertTrue({'valeur_mobilier', 'annee_construction', 'surface_m2'} <= att_mrh)
        self.assertNotIn('valeur_par_m2', att_mrh)
        self.assertNotIn('age_logement', att_mrh)
        print("    B1 colonnes_attendues : sources brutes (km/valeur/annee), pas les dérivées ✅")

    def test_colonnes_attendues_plan_sans_derivees(self):
        """Sur un plan SANS dérivées (RC Pro), colonnes_attendues == sources ∪
        obligatoires : aucune résolution parasite."""
        attendu = set(RCPRO.colonnes_sources()) | set(RCPRO.colonnes_obligatoires())
        if RCPRO.identifiant_contrat:
            attendu.add(RCPRO.identifiant_contrat)
        self.assertEqual(set(RCPRO.colonnes_attendues()), attendu)
        print("    B1 colonnes_attendues (plan sans dérivées) = sources ∪ obligatoires ✅")

    def test_correctif_4_complet_pour_mrh(self):
        """Le correctif #4 (valider_contre nomme la source) est désormais COMPLET :
        avant B1, _sources_brutes lisait DATA_DICTIONNAIRE (3/9) et ne traduisait
        PAS valeur_par_m2 ; via core.derivations (9/9), il nomme valeur_mobilier."""
        df = portefeuille_mrh(n=500).drop(columns=['valeur_mobilier'])
        with self.assertRaises(ValueError) as ctx:
            _a2().fit(df, MRH)
        msg = str(ctx.exception)
        self.assertIn('valeur_mobilier', msg,
            f"le message doit nommer la source brute valeur_mobilier : {msg}")
        print("    B1 complète le #4 : mrh sans valeur_mobilier → message nomme la source ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
