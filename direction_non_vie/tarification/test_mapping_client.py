"""
Moteur de mapping client (Phase 5, couche 1) — core/mapping_client.py.

Les 4 tests demandés + robustesse + preuve B1. Le fichier « client » est
portefeuille_auto renommé façon client (noms non-standard) : données réelles, bon
signal, bonnes modalités — le mapping le ramène aux noms du plan.
"""
import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from core.mapping_client import (
    MappingClient, MappingIncoherent, charger_mapping, valider_mapping,
    appliquer_mapping, preparer_fichier_client)
from direction_non_vie.tarification.test_plan_invariants import (
    AUTO, portefeuille_auto, _a2)

_RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
_MAPPING_EXEMPLE = os.path.join(_RACINE, 'mappings', 'client_exemple_auto.yaml')

# plan → client (inverse EXACT de mappings/client_exemple_auto.yaml)
PLAN_TO_CLIENT = {
    'age': 'AGE_CONDUCTEUR', 'bonus_malus': 'COEFF_BM',
    'anciennete_permis': 'ANC_PERMIS', 'puissance_fiscale': 'PUISSANCE_CV',
    'age_vehicule': 'AGE_VEHICULE', 'valeur_venale': 'VALEUR_VENALE',
    'garantie': 'FORMULE', 'carburant': 'ENERGIE', 'csp': 'CSP_CONDUCTEUR',
    'usage': 'USAGE_VEHICULE', 'antecedents_sinistres_n1': 'SIN_ANNEE_N1',
    'milieu_geographique': 'ZONE_GEO', 'kilometrage_annuel': 'KILOMETRAGE_AN',
    'exposition': 'DUREE_EXPO', 'nb_sinistres': 'NB_SINISTRES',
    'cout_total_sinistres': 'COUT_SINISTRES',
}


def _fichier_client(n=1500):
    return portefeuille_auto(n=n).rename(columns=PLAN_TO_CLIENT)


class TestMappingClient(unittest.TestCase):

    def test_1_mapping_complet(self):
        """Complet (16/16) → renommage correct, rapport propre, déclaratif PASSE."""
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        mapping = charger_mapping(_MAPPING_EXEMPLE)          # teste le chargement YAML
        df, rap = appliquer_mapping(_fichier_client(), mapping, AUTO)
        self.assertEqual(rap.n_renommees, 16)
        self.assertEqual(rap.colonnes_plan_non_couvertes, ())
        self.assertEqual(rap.colonnes_client_non_mappees, ())
        self.assertEqual(rap.correspondances_mortes, ())
        self.assertTrue(set(AUTO.colonnes_attendues()) <= set(df.columns))
        tarif = pipeline_complet(df, AUTO)
        self.assertGreater(tarif.glm_frequence.params.shape[0], 1)
        print("    MAP-1 complet : 16 renommées, 0 amputé, pipeline_complet passe ✅")

    def test_2_mapping_partiel_ampute(self):
        """Partiel (obligatoires + 1 facteur) → 12 attendues signalées ; chemin
        AGENT (A2.run) CONTINUE amputé (ne lève pas)."""
        from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
        partiel = MappingClient(client="Client Partiel", plan="auto.yaml",
            correspondances={'DUREE_EXPO': 'exposition', 'NB_SINISTRES': 'nb_sinistres',
                             'COUT_SINISTRES': 'cout_total_sinistres',
                             'AGE_CONDUCTEUR': 'age'})
        df, rap = appliquer_mapping(_fichier_client(), partiel, AUTO)
        self.assertEqual(rap.n_renommees, 4)
        self.assertEqual(len(rap.colonnes_plan_non_couvertes), 12)   # 16 − 4
        self.assertIn('bonus_malus', rap.colonnes_plan_non_couvertes)
        self.assertIn('kilometrage_annuel', rap.colonnes_plan_non_couvertes)
        self.assertIn('COEFF_BM', rap.colonnes_client_non_mappees)   # ignorée → candidate
        r1 = AgentA1Ingestion(audit_path='/tmp', verbose=False).run(
            dataframe=df, branche='non_vie', sous_branche='auto')
        r2 = _a2().run(r1, plan=AUTO)
        self.assertTrue(r2['success'], f"A2.run doit CONTINUER amputé : {r2.get('erreur')}")
        gap = r2.get('colonnes_plan_manquantes', {})
        self.assertTrue(gap.get('colonnes_non_produites') or gap.get('facteurs_absents'),
                        "A2.run doit SIGNALER l'amputation")
        print("    MAP-2 partiel : 4 renommées, 12 amputées signalées, A2.run continue ✅")

    def test_3_mapping_incoherent(self):
        """Cible ∉ plan (typo 'agee') → MappingIncoherent (erreur propre)."""
        mauvais = MappingClient(client="Client Typo", plan="auto.yaml",
            correspondances={'DUREE_EXPO': 'exposition', 'AGE_CONDUCTEUR': 'agee'})
        with self.assertRaises(MappingIncoherent) as ctx:
            valider_mapping(mauvais, AUTO)
        self.assertIn('agee', str(ctx.exception))
        print("    MAP-3 incohérent : cible 'agee' ∉ plan → MappingIncoherent ✅")

    def test_4_sans_mapping_retrocompatible(self):
        """Aucun mapping (None) → df inchangé, rap None, pipeline passe tel quel."""
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        df_canon = portefeuille_auto(n=1500)
        df, rap = preparer_fichier_client(df_canon, None, AUTO)
        self.assertIsNone(rap)
        self.assertIs(df, df_canon)
        tarif = pipeline_complet(df, AUTO)
        self.assertGreater(tarif.glm_frequence.params.shape[0], 1)
        print("    MAP-4 sans mapping : df inchangé, rap=None, pipeline passe ✅")

    def test_5_collision_cible(self):
        """Deux colonnes client → même cible → MappingIncoherent."""
        m = MappingClient(client="X", plan="auto.yaml", correspondances={'A': 'age', 'B': 'age'})
        with self.assertRaises(MappingIncoherent):
            valider_mapping(m, AUTO)
        print("    MAP-5 collision de cible → MappingIncoherent ✅")

    def test_6_collision_avec_existant(self):
        """Renommer vers une colonne DÉJÀ présente non-renommée → MappingIncoherent."""
        df = pd.DataFrame({'age': [30], 'AGE_COND': [40], 'exposition': [1.0],
                           'nb_sinistres': [0.0], 'cout_total_sinistres': [0.0]})
        m = MappingClient(client="X", plan="auto.yaml", correspondances={'AGE_COND': 'age'})
        with self.assertRaises(MappingIncoherent):
            appliquer_mapping(df, m, AUTO)
        print("    MAP-6 collision avec colonne existante → MappingIncoherent ✅")

    def test_7_correspondance_morte(self):
        """Clé du mapping absente du fichier → correspondances_mortes (pas fatal)."""
        m = MappingClient(client="X", plan="auto.yaml",
            correspondances={'DUREE_EXPO': 'exposition', 'COLONNE_ABSENTE': 'age'})
        _df, rap = appliquer_mapping(_fichier_client(n=50), m, AUTO)
        self.assertIn('COLONNE_ABSENTE', rap.correspondances_mortes)
        self.assertEqual(rap.n_renommees, 1)
        print("    MAP-7 correspondance morte signalée (pas fatale) ✅")

    def test_8_mauvais_plan(self):
        """mapping.plan ≠ plan fourni → MappingIncoherent (garde)."""
        m = MappingClient(client="X", plan="mrh.yaml",
                          correspondances={'DUREE_EXPO': 'exposition'})
        with self.assertRaises(MappingIncoherent):
            valider_mapping(m, AUTO)
        print("    MAP-8 mauvais plan (mrh sur auto) → MappingIncoherent ✅")

    def test_9_b1_kilometrage_cible_valide(self):
        """Preuve B1 : kilometrage_annuel (source de km_par_an_normalise) est une
        cible VALIDE — sans B1, colonnes_attendues aurait exigé la dérivée."""
        m = MappingClient(client="X", plan="auto.yaml",
                          correspondances={'KM': 'kilometrage_annuel'})
        valider_mapping(m, AUTO)   # ne lève pas
        self.assertIn('kilometrage_annuel', AUTO.colonnes_attendues())
        self.assertNotIn('km_par_an_normalise', AUTO.colonnes_attendues())
        print("    MAP-9 (B1) kilometrage_annuel cible valide, km_par_an_normalise non ✅")

    # ── couche 2 : câblage aux livrables ────────────────────────────────────
    def test_10_synthese_mapping(self):
        """Le libellé source-unique montre les 5 éléments ; None → None (rétro-compat)."""
        from core.mapping_client import synthese_mapping
        self.assertIsNone(synthese_mapping(None))
        partiel = MappingClient(client="ClientTest", plan="auto.yaml",
            correspondances={'DUREE_EXPO': 'exposition', 'NB_SINISTRES': 'nb_sinistres',
                             'COUT_SINISTRES': 'cout_total_sinistres', 'AGE_CONDUCTEUR': 'age',
                             'COLONNE_MORTE': 'bonus_malus'})
        _df, rap = appliquer_mapping(_fichier_client(n=50), partiel, AUTO)
        self.assertEqual(rap.n_colonnes_attendues, 16)
        self.assertEqual(rap.synthese()['n_colonnes_attendues'], 16)
        txt = synthese_mapping(rap)
        for attendu in ("ClientTest", "auto", "/16", "MODELE AMPUTE", "MORTE", "candidate"):
            self.assertIn(attendu, txt, f"'{attendu}' absent du libellé : {txt}")
        print("    MAP-10 synthese_mapping : client/plan/X-sur-N/amputé/morte/candidate ✅")

    def test_11_a6_transite_rapport_mapping(self):
        """A6.run TRANSITE rapport_mapping dans son résultat (→ 3 livrables), et
        exerce le rendu (export Excel/Word appelle synthese_mapping). None sinon."""
        from direction_non_vie.tarification.a4_ml.test_a4_ml import _make_r_a2, _make_r_a3
        from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
        from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
        from core.mapping_client import synthese_mapping
        r2, r3 = _make_r_a2(600), _make_r_a3()
        r4 = AgentA4ML(models_path='/tmp', audit_path='/tmp', verbose=False).run(
            result_a2=r2, result_a3=r3, plan=AUTO, calcul_shap=False, generer_graphiques=False)
        _df, rap = appliquer_mapping(_fichier_client(n=50),
            MappingClient(client="C", plan="auto.yaml",
                          correspondances={'DUREE_EXPO': 'exposition'}), AUTO)
        r6 = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp', verbose=False).run(
            result_a2=r2, result_a3=r3, result_a4=r4, rapport_mapping=rap,
            col_cible='nb_sinistres',   # A4 s'entraîne sur la fréquence par défaut
            generer_graphiques=False, generer_rapport_equipe=False, aide_decision=False)
        self.assertTrue(r6.get('success'), f"A6 doit réussir : {r6.get('erreur')}")
        self.assertIs(r6.get('rapport_mapping'), rap)
        self.assertIsNotNone(synthese_mapping(r6.get('rapport_mapping')))
        r6b = AgentA6Comparaison(models_path='/tmp', audit_path='/tmp', verbose=False).run(
            result_a2=r2, result_a3=r3, result_a4=r4, col_cible='nb_sinistres',
            generer_graphiques=False, generer_rapport_equipe=False, aide_decision=False)
        self.assertIsNone(r6b.get('rapport_mapping'))   # rétro-compat
        print("    MAP-11 A6 transite rapport_mapping (None sans mapping) ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
