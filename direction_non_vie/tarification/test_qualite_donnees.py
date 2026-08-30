"""
Tests de la couche qualité de données générique (core/qualite_donnees.py).

Vérifie les 4 règles, l'escalade (bloquée / confirmée-tracée), la dédup par
identifiant vs ligne, l'arrêt loud de pipeline_complet, ET — le plus important —
que TOUT est piloté par les RÔLES du plan (jamais un nom de colonne codé en dur) :
un plan aux colonnes arbitraires en bénéficie automatiquement.
"""
import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from core.plan_tarifaire import PlanTarifaire
from core.qualite_donnees import (
    controler_qualite, QualiteBloquante, synthese_qualite_donnees, SEUIL_ESCALADE,
)


def _plan(**kw):
    """Plan minimal (colonnes arbitraires possibles pour tester le pilotage par rôle)."""
    d = {'lob': 'test', 'exposition': 'exposition', 'cible_frequence': 'nb_sinistres',
         'cible_cout': 'cout_total_sinistres', 'facteurs': [{'nom': 'x', 'type': 'continu'}]}
    d.update(kw)
    return PlanTarifaire.depuis_dict(d)


def _df(n=100, **over):
    """Portefeuille PROPRE par défaut (aucune anomalie)."""
    d = pd.DataFrame({
        'x': np.linspace(1, 100, n),
        'exposition': np.linspace(0.6, 1.0, n),
        'nb_sinistres': (np.arange(n) % 2).astype(float),
        'cout_total_sinistres': np.where(np.arange(n) % 2 > 0, 3000., 0.),
        'id_contrat': np.arange(n),
    })
    for k, v in over.items():
        d[k] = v
    return d


class TestQualite_ReglesDeBase(unittest.TestCase):

    def test_propre_ne_touche_rien(self):
        df = _df(100)
        r = controler_qualite(df, _plan(), horodatage='2026-07-16T09:00:00')
        self.assertFalse(r.bloque)
        self.assertEqual(r.lignes_retenues, 100)
        self.assertEqual((len(r.exclusions), len(r.corrections), len(r.signalements)), (0, 0, 0))
        self.assertTrue(r.dataframe_propre.equals(df))
        self.assertIsNone(synthese_qualite_donnees(r))
        print("    QD-1 Propre → df intact, aucune action, synthèse None ✅")

    def test_regle1_impossible_exclut_la_ligne(self):
        df = _df(100)
        df['nb_sinistres'] = df['nb_sinistres'].astype(object)
        df['cout_total_sinistres'] = df['cout_total_sinistres'].astype(object)
        df['exposition'] = df['exposition'].astype(object)
        df.loc[[0, 1], 'nb_sinistres'] = -1.       # freq < 0
        df.loc[[2], 'cout_total_sinistres'] = -5.   # cout < 0
        df.loc[[3], 'exposition'] = 0.0             # expo <= 0 (casse l'offset)
        r = controler_qualite(df, _plan(), horodatage='t')
        codes = {a.code: a.nb_lignes for a in r.exclusions}
        self.assertEqual(codes.get('frequence_negative'), 2)
        self.assertEqual(codes.get('cout_negatif'), 1)
        self.assertEqual(codes.get('exposition_non_positive'), 1)
        self.assertEqual(r.lignes_retenues, 96)     # 4 lignes exclues
        self.assertFalse(r.bloque)
        print("    QD-2 Règle 1 (impossible) → 4 lignes exclues, comptées ✅")

    def test_regle2_implausible_corrige_et_signale(self):
        df = _df(100)
        df['exposition'] = df['exposition'].astype(object)
        df.loc[[10, 11], 'exposition'] = 1.5        # expo > 1
        r = controler_qualite(df, _plan(), horodatage='t')
        self.assertEqual([a.code for a in r.corrections], ['exposition_sup_1'])
        self.assertEqual(r.corrections[0].nb_lignes, 2)
        self.assertEqual(r.corrections[0].correction, 'plafond a 1.0')
        self.assertEqual(r.lignes_retenues, 100)    # corrigées, PAS exclues
        self.assertTrue((pd.to_numeric(r.dataframe_propre['exposition']) <= 1.0).all())
        print("    QD-3 Règle 2 (expo>1) → corrigée à 1.0, aucune exclusion ✅")

    def test_regle3_ambigu_signale_mais_laisse(self):
        df = _df(100)
        df['nb_sinistres'] = df['nb_sinistres'].astype(object)
        df['cout_total_sinistres'] = df['cout_total_sinistres'].astype(object)
        df.loc[[20, 21], 'cout_total_sinistres'] = 500.; df.loc[[20, 21], 'nb_sinistres'] = 0.  # cout>0 & freq=0
        df.loc[[30], 'nb_sinistres'] = 1.5          # non entière
        r = controler_qualite(df, _plan(), horodatage='t')
        codes = {a.code: a.nb_lignes for a in r.signalements}
        self.assertEqual(codes.get('incoherence_cout_sans_sin'), 2)
        self.assertEqual(codes.get('frequence_non_entiere'), 1)
        self.assertEqual(len(r.exclusions), 0)
        self.assertEqual(r.lignes_retenues, 100)    # rien retiré ni corrigé
        print("    QD-4 Règle 3 (ambigu) → signalé, compté, LAISSÉ (100/100) ✅")


class TestQualite_Escalade(unittest.TestCase):

    def test_seuil_depasse_sans_confirmation_bloque(self):
        df = _df(20)
        df['nb_sinistres'] = df['nb_sinistres'].astype(object)
        df.loc[[0, 1], 'nb_sinistres'] = -1.        # 2/20 = 10% >= 5%
        r = controler_qualite(df, _plan(), horodatage='t')
        self.assertTrue(r.bloque)
        self.assertIn('frequence_negative', r.anomalies_au_dela_seuil)
        self.assertIsNone(r.dataframe_propre)
        self.assertIn('BLOQUE', synthese_qualite_donnees(r))
        print("    QD-5 Escalade ≥5% sans confirmation → bloqué, df None ✅")

    def test_seuil_depasse_avec_confirmation_poursuit_et_trace(self):
        df = _df(20)
        df['nb_sinistres'] = df['nb_sinistres'].astype(object)
        df.loc[[0, 1], 'nb_sinistres'] = -1.
        r = controler_qualite(df, _plan(), qualite_validee_par='Marie Durand',
                              horodatage='2026-07-16T09:00:00')
        self.assertFalse(r.bloque)
        self.assertEqual(r.validee_par, 'Marie Durand')
        self.assertEqual(r.lignes_retenues, 18)     # 2 exclues, poursuit
        s = synthese_qualite_donnees(r)
        self.assertIn('Marie Durand', s)
        self.assertIn('16/07/2026', s)              # date réutilisée, reformatée
        print("    QD-6 Escalade ≥5% confirmée → poursuit + trace nominative datée ✅")

    def test_seuil_parametrable(self):
        df = _df(20)
        df['nb_sinistres'] = df['nb_sinistres'].astype(object)
        df.loc[[0, 1], 'nb_sinistres'] = -1.        # 10%
        # seuil relevé à 50% → 10% ne déclenche plus l'escalade
        r = controler_qualite(df, _plan(), seuil_escalade=0.50, horodatage='t')
        self.assertFalse(r.bloque)
        self.assertEqual(r.lignes_retenues, 18)     # traité au niveau ligne, continue
        self.assertEqual(SEUIL_ESCALADE, 0.05)      # le défaut reste 5%
        print("    QD-7 Seuil paramétrable (0.50) → 10% ne bloque plus ; défaut=0.05 ✅")


class TestQualite_Doublons(unittest.TestCase):

    def test_doublon_identifiant_declare_regle1(self):
        """⚠️⚠️ MIS A JOUR LE 30/08/2026 — LA REGLE A CHANGE, PAS LE TEST.

        Il prouvait qu'un identifiant DECLARE rend le dedoublonnage plus fin
        que `doublon_ligne`. Il le prouve toujours — mais la clef complete est
        desormais la PAIRE `(identifiant, echeance)` : sans echeance on ne peut
        pas distinguer un doublon d'un HISTORIQUE de renouvellement (mesure :
        66,7 % de faux doublons sur 3 exercices), et la constatation devient
        AMBIGUE, donc regle 3. Les deux cas sont epingles ci-dessous plutot que
        l'ancien seul.
        """
        df = _df(50)
        df = pd.concat([df, df.iloc[[5, 6]]], ignore_index=True)   # 2 doublons (id inclus)

        # ① CLEF COMPLETE : meme contrat, MEME echeance -> impossible, exclu.
        plan = _plan(identifiant_contrat='id_contrat', echeance='annee')
        r = controler_qualite(df.assign(annee=2025), plan, horodatage='t')
        excl = {a.code: a.nb_lignes for a in r.exclusions}
        self.assertEqual(excl.get('doublon_identifiant'), 2)
        self.assertEqual(r.lignes_retenues, 50)     # 52 - 2 exclus

        # ② SANS ECHEANCE : ambigu -> signale, et les lignes RESTENT.
        r2 = controler_qualite(df, _plan(identifiant_contrat='id_contrat'),
                               horodatage='t', qualite_validee_par='ctrl')
        sig = {a.code: a.nb_lignes for a in r2.signalements}
        self.assertEqual(sig.get('doublon_identifiant_sans_echeance'), 2)
        self.assertEqual([a.code for a in r2.exclusions], [])
        self.assertEqual(r2.lignes_retenues, 52)
        print("    QD-8 Doublon : avec echeance → règle 1 (exclu) ; sans "
              "echeance → règle 3 (signalé, conservé) ✅")

    def test_doublon_ligne_sans_identifiant_regle3(self):
        df = _df(50)
        df = pd.concat([df, df.iloc[[5, 6]]], ignore_index=True)
        r = controler_qualite(df, _plan(), horodatage='t')   # pas d'identifiant_contrat
        sig = {a.code: a.nb_lignes for a in r.signalements}
        self.assertEqual(sig.get('doublon_ligne'), 2)
        self.assertFalse(any(a.code.startswith('doublon') for a in r.exclusions))
        self.assertEqual(r.lignes_retenues, 52)     # signalé, PAS exclu
        print("    QD-9 Doublon de ligne SANS identifiant → règle 3 (signalé, laissé) ✅")


class TestQualite_PiloteParLePlan(unittest.TestCase):

    def test_detection_sur_colonnes_arbitraires_du_plan(self):
        """Le cœur du contrat : les rôles du plan pilotent, pas des noms codés.
        Un plan aux colonnes 'duree'/'claims'/'charge' est contrôlé sur CELLES-CI."""
        plan = _plan(exposition='duree', cible_frequence='claims', cible_cout='charge')
        df = pd.DataFrame({
            'x': [1., 2., 3., 4.],
            'duree': [0.8, -0.5, 1.4, 0.9],    # -0.5 impossible (r1), 1.4 corrigé (r2)
            'claims': [0., 1., -2., 3.],        # -2 impossible (r1)
            'charge': [0., 500., 100., 900.],
        })
        r = controler_qualite(df, plan, horodatage='t')
        excl = {a.code for a in r.exclusions}
        corr = {a.code for a in r.corrections}
        self.assertIn('exposition_non_positive', excl)   # détecté sur 'duree'
        self.assertIn('frequence_negative', excl)        # détecté sur 'claims'
        self.assertIn('exposition_sup_1', corr)          # 'duree'=1.4 corrigé
        # colonnes réelles tracées = celles du plan, pas des noms codés en dur
        roles = {a.role: a.colonne for a in (r.exclusions + r.corrections)}
        self.assertEqual(roles.get('exposition'), 'duree')
        self.assertEqual(roles.get('cible_frequence'), 'claims')
        print("    QD-10 Piloté par les RÔLES du plan (duree/claims/charge), pas par nom ✅")

    def test_pipeline_complet_leve_QualiteBloquante(self):
        """Bout-en-bout : une anomalie ≥5% non validée ARRÊTE pipeline_complet
        (loud), au lieu de tarifer en silence sur des données impossibles."""
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        plan = PlanTarifaire.depuis_yaml(
            os.path.join(os.path.dirname(__file__), '..', '..', 'plans', 'decennale.yaml'))
        rng = np.random.default_rng(0); n = 200
        nb = rng.integers(0, 2, n).astype(float)
        df = pd.DataFrame({
            'montant_travaux_eur': rng.uniform(2e4, 2e5, n), 'nb_lots': rng.integers(1, 10, n).astype(float),
            'anciennete_entreprise_ans': rng.integers(0, 30, n).astype(float),
            'type_ouvrage': rng.choice(['Maison', 'Collectif', 'Tertiaire'], n),
            'qualification_entreprise': rng.choice(['Qualibat', 'Non qualifie'], n),
            'nature_marche': rng.choice(['Prive', 'Public'], n),
            'sinistres_3ans_anterieurs': rng.integers(0, 3, n).astype(float),
            'exposition': rng.uniform(0.6, 1.0, n), 'nb_sinistres': nb,
            'cout_total_sinistres': np.where(nb > 0, rng.gamma(2, 12000, n), 0.).astype(object)})
        df.loc[list(range(20)), 'cout_total_sinistres'] = -100.   # 10% cout<0
        with self.assertRaises(QualiteBloquante):
            pipeline_complet(df, plan, equilibrer=False)
        # avec confirmation nominative → passe (l'échappatoire tracée)
        t = pipeline_complet(df, plan, equilibrer=False, qualite_validee_par='Actuaire X')
        self.assertTrue(t.rapport_qualite.validee_par == 'Actuaire X')
        print("    QD-11 pipeline_complet ≥5% → QualiteBloquante ; confirmé → passe + trace ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
