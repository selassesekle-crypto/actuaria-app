"""
Tests du proposeur LLM de mapping (core/mapping_llm.py).

Les tests unitaires MOCKENT l'appel API (aucun réseau, aucune clé requise) en
patchant _appeler_claude — la frontière `anthropic`. Un test d'INTÉGRATION réel
n'est actif que si la clé ET le paquet anthropic sont présents (@skipUnless) :
il ne tourne pas dans la suite courante, il sert de preuve de bout en bout.
"""
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import core.mapping_llm as mapping_llm
from core.mapping_llm import proposer_mapping, MappingLLMIndisponible
from core.mapping_client import MappingClient, MappingIncoherent
from core.plan_tarifaire import PlanTarifaire
from direction_non_vie.tarification.test_plan_invariants import portefeuille_auto

_RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
_PLAN_AUTO = os.path.join(_RACINE, 'plans', 'auto.yaml')

# fichier client = portefeuille_auto renommé en anglais (noms non-standard)
_PLAN_TO_EN = {
    'age': 'driver_age', 'bonus_malus': 'bonus_coeff',
    'anciennete_permis': 'licence_years', 'puissance_fiscale': 'fiscal_power',
    'age_vehicule': 'vehicle_age', 'valeur_venale': 'market_value',
    'garantie': 'coverage', 'carburant': 'fuel', 'csp': 'social_class',
    'usage': 'usage', 'antecedents_sinistres_n1': 'claims_prev_year',
    'milieu_geographique': 'geo_area', 'kilometrage_annuel': 'annual_mileage',
    'exposition': 'exposure', 'nb_sinistres': 'claim_count',
    'cout_total_sinistres': 'claim_cost',
}


def _client_en(n=200):
    return portefeuille_auto(n=n).rename(columns=_PLAN_TO_EN)


def _anthropic_dispo() -> bool:
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


class TestProposerMapping(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.plan = PlanTarifaire.depuis_yaml(_PLAN_AUTO)
        cls.df = _client_en()

    def test_1_mock_json_valide_donne_mapping_coherent(self):
        """Mock : JSON valide → MappingClient cohérent, cibles ⊆ attendues."""
        propose = {
            'exposure': 'exposition', 'claim_count': 'nb_sinistres',
            'claim_cost': 'cout_total_sinistres', 'driver_age': 'age',
            'coverage': 'garantie', 'annual_mileage': 'kilometrage_annuel',
        }
        with patch.object(mapping_llm, '_appeler_claude',
                          return_value=json.dumps(propose)):
            mapping = proposer_mapping(self.df, self.plan)
        self.assertIsInstance(mapping, MappingClient)
        self.assertEqual(mapping.correspondances['exposure'], 'exposition')
        self.assertEqual(mapping.correspondances['claim_count'], 'nb_sinistres')
        self.assertTrue(
            set(mapping.correspondances.values()) <= set(self.plan.colonnes_attendues()))
        print(f"    LLM-1 mock JSON valide : {len(mapping.correspondances)} "
              f"correspondances, cohérent ✅")

    def test_2_mock_cible_invalide_leve_incoherent(self):
        """Mock : cible ABSENTE du plan → MappingIncoherent (même garde-fou que
        le mapping manuel)."""
        propose = {'exposure': 'exposition', 'driver_age': 'age_conducteur_XXX'}
        with patch.object(mapping_llm, '_appeler_claude',
                          return_value=json.dumps(propose)):
            with self.assertRaises(MappingIncoherent):
                proposer_mapping(self.df, self.plan)
        print("    LLM-2 mock cible invalide : MappingIncoherent levée ✅")

    def test_3_erreur_api_propre(self):
        """Mock : l'appel API échoue → MappingLLMIndisponible (jamais un crash)."""
        def _boom(*a, **k):
            raise MappingLLMIndisponible("service de proposition indisponible")
        with patch.object(mapping_llm, '_appeler_claude', side_effect=_boom):
            with self.assertRaises(MappingLLMIndisponible):
                proposer_mapping(self.df, self.plan)
        print("    LLM-3 erreur API : MappingLLMIndisponible (erreur propre) ✅")

    def test_4_mock_reponse_illisible_propre(self):
        """Mock : réponse non-JSON → MappingLLMIndisponible (pas de crash)."""
        with patch.object(mapping_llm, '_appeler_claude',
                          return_value="desole, je ne peux pas produire ce mapping"):
            with self.assertRaises(MappingLLMIndisponible):
                proposer_mapping(self.df, self.plan)
        print("    LLM-4 réponse illisible : MappingLLMIndisponible ✅")

    @unittest.skipUnless(
        os.environ.get('ANTHROPIC_API_KEY') and _anthropic_dispo(),
        "clé ANTHROPIC_API_KEY et/ou paquet anthropic absents — "
        "intégration réelle ignorée")
    def test_5_integration_reelle(self):
        """INTÉGRATION RÉELLE (clé + paquet requis) : vrai appel Claude sur un
        fichier auto renommé en anglais ; le mapping proposé doit être cohérent
        et rapprocher au moins les cibles + l'exposition."""
        mapping = proposer_mapping(self.df, self.plan)
        self.assertIsInstance(mapping, MappingClient)
        cibles = set(mapping.correspondances.values())
        self.assertIn('exposition', cibles)
        self.assertIn('nb_sinistres', cibles)
        self.assertIn('cout_total_sinistres', cibles)
        print(f"    LLM-5 intégration réelle : {len(mapping.correspondances)} "
              f"correspondances proposées ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
