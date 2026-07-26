# =============================================================================
#  Tests — nv_triangle_mapping.py (Bloc II, module 2)
#
#  Cœur : la désambiguïsation payé / charge / évaluation courante, et le fait
#  que N'IMPORTE QUELLE méthode puisse tourner sur les charges (pas seulement
#  Munich CL). Les 5 cas des trois briques (classe T2) sont le centre de gravité.
# =============================================================================

import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from direction_non_vie.services.nv_triangle_mapping import (
    CHAMPS_SINISTRES, CHAMPS_PRIMES,
    TriangleSchema, RapportMappingTriangle, MappingTriangleIncoherent,
    charger_mapping_triangle, valider_mapping_triangle,
    appliquer_mapping_triangle, preparer_tableau, capacites,
)


def _schema(corr, kind='sinistres'):
    return TriangleSchema(kind=kind, correspondances=corr, source='test')


class T1_Contrat_Mapping(unittest.TestCase):
    """Contrat de base — validation statique et garde-fous."""

    def test_mapping_valide_complet(self):
        df = pd.DataFrame({'AY': [2020], 'DEV': [0], 'PAID': [100.0]})
        df_r, rap = appliquer_mapping_triangle(
            df, _schema({'AY': 'annee_survenance', 'DEV': 'annee_developpement',
                         'PAID': 'montant_paye'}))
        self.assertIn('montant_paye', df_r.columns)
        self.assertEqual(rap.n_renommees, 3)
        self.assertEqual(set(rap.champs_couverts),
                         {'annee_survenance', 'annee_developpement', 'montant_paye'})
        print("    OK T1a mapping valide complet : 3 colonnes renommées")

    def test_cible_inconnue_leve(self):
        with self.assertRaises(MappingTriangleIncoherent):
            valider_mapping_triangle(_schema({'A': 'montnat_paye'}))  # typo
        print("    OK T1b cible inconnue → lève")

    def test_doublon_de_cible_leve(self):
        with self.assertRaises(MappingTriangleIncoherent):
            valider_mapping_triangle(_schema({'A': 'montant_paye', 'B': 'montant_paye'}))
        print("    OK T1c deux colonnes → même cible → lève")

    def test_collision_au_renommage_leve(self):
        df = pd.DataFrame({'A': [2020], 'montant_paye': [100.0]})
        with self.assertRaises(MappingTriangleIncoherent):
            appliquer_mapping_triangle(df, _schema({'A': 'montant_paye'}))  # collision
        print("    OK T1d renommage créant un doublon → lève")

    def test_survenance_absente_fatale(self):
        df = pd.DataFrame({'DEV': [0], 'PAID': [100.0]})
        with self.assertRaises(MappingTriangleIncoherent):
            appliquer_mapping_triangle(
                df, _schema({'DEV': 'annee_developpement', 'PAID': 'montant_paye'}))
        print("    OK T1e annee_survenance absente → fatal")

    def test_aucune_mesure_fatale(self):
        df = pd.DataFrame({'AY': [2020], 'DEV': [0]})
        with self.assertRaises(MappingTriangleIncoherent):
            appliquer_mapping_triangle(
                df, _schema({'AY': 'annee_survenance', 'DEV': 'annee_developpement'}))
        print("    OK T1f aucune mesure → fatal")

    def test_correspondances_mortes_tracees(self):
        df = pd.DataFrame({'AY': [2020], 'PAID': [100.0]})
        _, rap = appliquer_mapping_triangle(
            df, _schema({'AY': 'annee_survenance', 'PAID': 'montant_paye',
                         'GHOST': 'annee_developpement'}))
        self.assertEqual(rap.correspondances_mortes, ('GHOST',))
        print("    OK T1g clé de mapping absente du fichier → correspondances_mortes")

    def test_passthrough_reconnait_les_noms(self):
        df = pd.DataFrame({'accident_year': [2020], 'dev': [0], 'paid': [100.0]})
        df_r, rap = preparer_tableau(df, None, kind='sinistres')
        self.assertIn('montant_paye', df_r.columns)
        self.assertIn('annee_survenance', df_r.columns)
        self.assertTrue(rap.peut_construire_paiements)
        print("    OK T1h passthrough : colonnes reconnues par leur nom")

    def test_round_trip_yaml(self):
        tmp = Path(tempfile.mkdtemp(prefix='nvmap_'))
        try:
            (tmp / 'm.yaml').write_text(
                "kind: sinistres\ncorrespondances:\n  AY: annee_survenance\n"
                "  DEV: annee_developpement\n  PAID: montant_paye\n", encoding='utf-8')
            sch = charger_mapping_triangle(tmp / 'm.yaml')
            self.assertEqual(sch.kind, 'sinistres')
            self.assertEqual(sch.correspondances['PAID'], 'montant_paye')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print("    OK T1i round-trip YAML")


class T2_Trois_Briques(unittest.TestCase):
    """CŒUR — les trois briques et l'indépendance des bases : n'importe quelle
    méthode doit pouvoir tourner sur paiements OU charges, pas seulement Munich."""

    def test_paiements_seuls(self):
        caps = capacites(['annee_survenance', 'annee_developpement', 'montant_paye'])
        self.assertTrue(caps['peut_construire_paiements'])
        self.assertFalse(caps['peut_construire_charges'])
        self.assertFalse(caps['peut_deriver_charges'])
        print("    OK T2a paiements seuls : paiements=True, charges=False")

    def test_charges_seules_chain_ladder_sans_munich(self):
        """Le cas de la précision Selasse : un actuaire veut tourner Chain Ladder
        sur les CHARGES sans Munich CL. La base charges doit être annoncée
        disponible SANS exiger les paiements."""
        caps = capacites(['annee_survenance', 'annee_developpement', 'montant_charge'])
        self.assertTrue(caps['peut_construire_charges'])
        self.assertFalse(caps['peut_construire_paiements'])
        self.assertFalse(caps['peut_deriver_charges'])
        print("    OK T2b charges seules : charges=True, paiements=False (CL sur charges OK)")

    def test_paiements_et_charges(self):
        caps = capacites(['annee_survenance', 'annee_developpement',
                          'montant_paye', 'montant_charge'])
        self.assertTrue(caps['peut_construire_paiements'])
        self.assertTrue(caps['peut_construire_charges'])
        print("    OK T2c paiements + charges : les deux bases + Munich possibles")

    def test_paiements_plus_evaluation_derive_charges(self):
        caps = capacites(['annee_survenance', 'annee_developpement',
                          'montant_paye', 'evaluation_courante'])
        self.assertTrue(caps['peut_construire_paiements'])
        self.assertFalse(caps['peut_construire_charges'])   # pas de montant_charge direct
        self.assertTrue(caps['peut_deriver_charges'])        # charges = paiements + provisions
        print("    OK T2d paiements + évaluation : dérivation des charges possible")

    def test_provisions_seules_non_fatal_mais_rien_de_direct(self):
        """Une table provisions (survenance + evaluation, SANS axe) ne construit
        rien seule, mais n'est PAS fatale : c'est la 3e brique, combinée en aval."""
        df = pd.DataFrame({'AY': [2020], 'PROV': [500.0]})
        _, rap = appliquer_mapping_triangle(
            df, _schema({'AY': 'annee_survenance', 'PROV': 'evaluation_courante'}))
        self.assertFalse(rap.peut_construire_paiements)
        self.assertFalse(rap.peut_construire_charges)
        self.assertFalse(rap.peut_deriver_charges)           # pas de paiements ici
        self.assertIn('evaluation_courante', rap.champs_couverts)
        print("    OK T2e provisions seules : non fatal, rien de constructible seul")


class T2b_Table_Tout_En_Un(unittest.TestCase):
    """Table « tout en un » — sinistres ET une colonne de primes dans le MÊME
    tableau. Le passthrough retenait toutes les colonnes reconnues sans filtrer
    par kind : la colonne prime était proposée en cible d'un mapping sinistres
    (et inversement) → la validation levait alors que rien n'est anormal."""

    # une ligne par sinistre/période + la prime de l'année, répétée
    DF = pd.DataFrame({
        'annee_survenance': [2020, 2020, 2021],
        'dev':              [0, 1, 0],
        'paid':             [100.0, 150.0, 120.0],
        'incurred':         [180.0, 175.0, 200.0],
        'prime':            [5000.0, 5000.0, 5200.0],
    })

    def test_passthrough_sinistres_ignore_la_prime(self):
        """kind='sinistres' : la colonne prime est ignorée, pas fatale."""
        df_r, rap = preparer_tableau(self.DF, None, kind='sinistres')
        self.assertEqual(set(rap.champs_couverts),
                         {'annee_survenance', 'annee_developpement',
                          'montant_paye', 'montant_charge'})
        self.assertIn('prime', rap.colonnes_client_non_mappees)
        self.assertNotIn('prime', df_r.columns[df_r.columns.isin(CHAMPS_SINISTRES)])
        self.assertTrue(rap.peut_construire_paiements)
        self.assertTrue(rap.peut_construire_charges)
        print("    OK T2f tout-en-un / sinistres : prime ignorée, 2 bases constructibles")

    def test_passthrough_primes_ignore_les_colonnes_sinistres(self):
        """kind='primes' sur LA MÊME table : symétrique, les colonnes de
        sinistres sont ignorées."""
        _, rap = preparer_tableau(self.DF, None, kind='primes')
        self.assertEqual(set(rap.champs_couverts), {'annee_survenance', 'prime'})
        for col in ('dev', 'paid', 'incurred'):
            self.assertIn(col, rap.colonnes_client_non_mappees)
        print("    OK T2g tout-en-un / primes : colonnes sinistres ignorées")

    def test_double_passe_sur_la_meme_table(self):
        """Effet direct du correctif : la même table se lit en sinistres PUIS en
        primes, chaque passe ne voyant que son vocabulaire."""
        _, r_sin = preparer_tableau(self.DF, None, kind='sinistres')
        _, r_pri = preparer_tableau(self.DF, None, kind='primes')
        self.assertIn('montant_paye', r_sin.champs_couverts)
        self.assertNotIn('prime', r_sin.champs_couverts)
        self.assertIn('prime', r_pri.champs_couverts)
        self.assertNotIn('montant_paye', r_pri.champs_couverts)
        print("    OK T2h double passe : sinistres puis primes sur la même table")

    def test_mapping_explicite_inchange(self):
        """Non-régression : le correctif ne touche QUE le passthrough. Un mapping
        EXPLICITE visant 'prime' en kind='sinistres' doit toujours LEVER."""
        with self.assertRaises(MappingTriangleIncoherent):
            appliquer_mapping_triangle(self.DF, _schema(
                {'annee_survenance': 'annee_survenance', 'prime': 'prime'}))
        print("    OK T2i mapping explicite hors vocabulaire : lève toujours")


class T3_Desambiguisation(unittest.TestCase):
    """Payé / charge / évaluation ne se confondent plus ; l'ambigu est signalé."""

    def test_paid_vers_montant_paye(self):
        self.assertEqual(capacites(['paid'])['champs_reconnus'], ['montant_paye'])
        print("    OK T3a 'paid' → montant_paye")

    def test_incurred_vers_montant_charge(self):
        self.assertEqual(capacites(['incurred'])['champs_reconnus'], ['montant_charge'])
        print("    OK T3b 'incurred' → montant_charge")

    def test_montant_ambigu_rattache_aux_paiements_avec_alerte(self):
        df = pd.DataFrame({'accident_year': [2020], 'dev': [0], 'montant': [100.0]})
        df_r, rap = preparer_tableau(df, None)
        self.assertIn('montant_paye', df_r.columns)          # rattaché aux paiements
        self.assertIn('montant', rap.mesures_ambigues)        # mais SIGNALÉ
        # et capacites() le voit aussi ambigu
        self.assertIn('montant', capacites(df)['mesures_ambigues'])
        print("    OK T3c 'montant' seul → montant_paye + signalé ambigu (non silencieux)")


class T4_Primes(unittest.TestCase):
    """Table de primes : vocabulaire propre, obligations propres."""

    def test_primes_valide(self):
        df = pd.DataFrame({'AY': [2020], 'PREM': [1000.0]})
        _, rap = appliquer_mapping_triangle(
            df, _schema({'AY': 'annee_survenance', 'PREM': 'prime'}, kind='primes'))
        self.assertEqual(set(rap.champs_couverts), {'annee_survenance', 'prime'})
        print("    OK T4a primes valides : survenance + prime")

    def test_prime_manquante_fatale(self):
        df = pd.DataFrame({'AY': [2020]})
        with self.assertRaises(MappingTriangleIncoherent):
            appliquer_mapping_triangle(
                df, _schema({'AY': 'annee_survenance'}, kind='primes'))
        print("    OK T4b prime manquante → fatal")


class T5_Forme(unittest.TestCase):
    """Verrou anti-dérive : le contrat public reste stable (sans coupler au tarif)."""

    def test_synthese_json_serialisable_et_cles_stables(self):
        df = pd.DataFrame({'AY': [2020], 'DEV': [0], 'PAID': [100.0]})
        _, rap = appliquer_mapping_triangle(
            df, _schema({'AY': 'annee_survenance', 'DEV': 'annee_developpement',
                         'PAID': 'montant_paye'}))
        s = rap.synthese()
        import json
        json.dumps(s)   # doit être sérialisable
        for cle in ('peut_construire_paiements', 'peut_construire_charges',
                    'peut_deriver_charges', 'champs_couverts', 'mesures_ambigues'):
            self.assertIn(cle, s)
        print("    OK T5a synthese() json-sérialisable, clés de capacité présentes")

    def test_vocabulaire_desambigue(self):
        # la désambiguïsation EST le point : payé et charge sont deux champs distincts
        self.assertIn('montant_paye', CHAMPS_SINISTRES)
        self.assertIn('montant_charge', CHAMPS_SINISTRES)
        self.assertNotIn('montant', CHAMPS_SINISTRES)   # l'ambigu n'est pas canonique
        self.assertEqual(CHAMPS_PRIMES, frozenset({'annee_survenance', 'prime'}))
        print("    OK T5b vocabulaire : montant_paye ≠ montant_charge, 'montant' non canonique")


if __name__ == '__main__':
    unittest.main()
