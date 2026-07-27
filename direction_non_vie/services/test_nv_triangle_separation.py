# =============================================================================
#  Tests — nv_triangle_separation.py (Bloc II, module 5)
#
#  Trois points de gravité :
#   (a) le sinistre payé en PLUSIEURS lignes, correctement regroupé par
#       sinistre_id (sans quoi il passerait sous le seuil) ;
#   (b) le sinistre JEUNE, mal classé sur le payé seul et bien classé sur la
#       charge — c'est l'enjeu de la hiérarchie de classement ;
#   (c) le chaînage réel avec le module 4 : C_attrit + C_grands = C_total, la
#       preuve que la séparation n'invente ni ne perd de montant.
#  Plus le VERROU DE PÉRIMÈTRE : la sortie ne porte AUCUN champ de réserve.
# =============================================================================

import dataclasses
import json
import unittest

import numpy as np
import pandas as pd

from direction_non_vie.services.nv_triangle_separation import (
    BASES_CLASSEMENT, SeparationImpossible, SeparationLLT,
    avertir_si_agregat, separer_par_seuil,
)
from direction_non_vie.services.nv_triangle_construction import construire_triangles

# ── Fixtures ─────────────────────────────────────────────────────────────────
# Sinistre S1 : réglé en TROIS versements de 400 (total 1200) → grand si seuil 1000,
#               mais AUCUNE ligne ne dépasse 1000 prise isolément.
# Sinistre S2 : une ligne de 100 → attritionnel.
# Sinistre S3 : une ligne de 2000 → grand quelle que soit la maille.
LONG = pd.DataFrame({
    'sinistre_id':         ['S1', 'S1', 'S1', 'S2', 'S3'],
    'annee_survenance':    [2020, 2020, 2021, 2021, 2022],
    'annee_developpement': [0, 1, 0, 0, 0],
    'montant_paye':        [400., 400., 400., 100., 2000.],
})

# Sinistre JEUNE : peu payé (50) mais lourdement provisionné (5000).
JEUNE = pd.DataFrame({
    'sinistre_id':         ['J1', 'A1'],
    'annee_survenance':    [2022, 2020],
    'annee_developpement': [0, 0],
    'montant_paye':        [50., 300.],
    'evaluation_courante': [5000., 0.],
})

MATRICE = np.array([[100., 150.], [120., 0.]])


class T1_Classement_Par_Sinistre(unittest.TestCase):
    """(a) Le piège du sinistre réglé en plusieurs versements."""

    def test_sinistre_en_plusieurs_lignes_regroupe(self):
        """S1 = 3 × 400 = 1200 ≥ 1000 : grand, alors qu'AUCUNE de ses lignes
        n'atteint le seuil. Sans regroupement par sinistre_id, il serait raté."""
        r = separer_par_seuil(LONG, 1000.)
        self.assertTrue(r.classement_par_sinistre)
        self.assertEqual(set(r.grands['sinistre_id']), {'S1', 'S3'})
        self.assertEqual(set(r.attritionnel['sinistre_id']), {'S2'})
        self.assertEqual(r.n_grands, 4)            # 3 lignes S1 + 1 ligne S3
        self.assertEqual(r.n_attritionnels, 1)
        print("    OK T1a S1 (3×400=1200) reconnu grand : regroupement par sinistre_id")

    def test_sans_identifiant_le_classement_degrade_est_alerte(self):
        """Sans sinistre_id : classement ligne à ligne — S1 n'est PLUS détecté,
        et l'alerte le dit explicitement."""
        r = separer_par_seuil(LONG.drop(columns=['sinistre_id']), 1000.)
        self.assertFalse(r.classement_par_sinistre)
        self.assertEqual(r.n_grands, 1)            # seule la ligne de 2000
        self.assertTrue(any("'sinistre_id' absente" in a for a in r.rapport['alertes']))
        print("    OK T1b sans sinistre_id : S1 raté (1 seul grand) + alerte dégradé")

    def test_liste_des_grands_une_ligne_par_dossier(self):
        r = separer_par_seuil(LONG, 1000.)
        liste = r.sinistres_grands
        self.assertEqual(list(liste.columns),
                         ['sinistre_id', 'cout_retenu', 'annee_survenance'])
        self.assertEqual(len(liste), 2)                       # S3 et S1, pas 4 lignes
        self.assertEqual(liste.iloc[0]['sinistre_id'], 'S3')  # trié par coût décroissant
        self.assertAlmostEqual(float(liste.iloc[0]['cout_retenu']), 2000., places=2)
        self.assertAlmostEqual(
            float(liste[liste['sinistre_id'] == 'S1']['cout_retenu'].iloc[0]), 1200.)
        print("    OK T1c liste actuaire : 1 ligne par dossier, coût total, triée")

    def test_seuil_inclus_convention(self):
        """Convention figée : le seuil est INCLUS (>=)."""
        exact = separer_par_seuil(LONG, 1200.)      # S1 vaut exactement 1200
        self.assertIn('S1', set(exact.grands['sinistre_id']))
        juste_au_dessus = separer_par_seuil(LONG, 1200.01)
        self.assertNotIn('S1', set(juste_au_dessus.grands['sinistre_id']))
        print("    OK T1d seuil INCLUS : 1200 ≥ 1200 grand, 1200 < 1200.01 attritionnel")


class T2_Base_De_Classement(unittest.TestCase):
    """(b) Le sinistre jeune : mal classé sur le payé, bien classé sur la charge."""

    def test_jeune_sous_classe_sur_le_paye_seul(self):
        """Payé seul : J1 (50 payé, 5000 provisionné) est jugé ATTRITIONNEL —
        exactement le sinistre qu'il fallait isoler. L'alerte doit le dire."""
        r = separer_par_seuil(JEUNE.drop(columns=['evaluation_courante']), 1000.)
        self.assertEqual(r.base_classement_utilisee, 'paye')
        self.assertEqual(r.n_grands, 0)                        # J1 raté
        self.assertTrue(any('SOUS-CLASSÉS' in a for a in r.rapport['alertes']))
        print("    OK T2a payé seul : J1 (50 payé / 5000 provisionné) raté + alerte")

    def test_jeune_correctement_classe_avec_la_provision(self):
        """Payé + provision : J1 vaut 5050 ≥ 1000 → correctement classé grand."""
        r = separer_par_seuil(JEUNE, 1000.)
        self.assertEqual(r.base_classement_utilisee, 'paye_plus_provision')
        self.assertEqual(set(r.grands['sinistre_id']), {'J1'})
        print("    OK T2b payé + provision : J1 correctement classé grand (5050)")

    def test_charge_est_prioritaire(self):
        avec_charge = JEUNE.assign(montant_charge=[5050., 300.])
        r = separer_par_seuil(avec_charge, 1000.)
        self.assertEqual(r.base_classement_utilisee, 'charge')
        self.assertEqual(set(r.grands['sinistre_id']), {'J1'})
        print("    OK T2c montant_charge prioritaire sur les autres bases")

    def test_base_forcee_et_base_inconnue(self):
        r = separer_par_seuil(JEUNE, 1000., base_classement='paye')
        self.assertEqual(r.base_classement_utilisee, 'paye')   # forçage respecté
        with self.assertRaises(SeparationImpossible):
            separer_par_seuil(JEUNE, 1000., base_classement='fantaisie')
        print("    OK T2d base forçable ; base inconnue → lève")

    def test_aucune_mesure_leve(self):
        df = pd.DataFrame({'sinistre_id': ['X'], 'annee_survenance': [2020],
                           'annee_developpement': [0]})
        with self.assertRaises(SeparationImpossible):
            separer_par_seuil(df, 1000.)
        print("    OK T2e aucune mesure exploitable → lève")


class T3_Coherence(unittest.TestCase):
    """Rien n'est perdu, rien n'est dupliqué."""

    def test_partition_exacte_des_lignes(self):
        r = separer_par_seuil(LONG, 1000.)
        self.assertEqual(r.n_grands + r.n_attritionnels, len(LONG))
        # union des index = index source, intersection vide
        idx = set(r.attritionnel.index) | set(r.grands.index)
        self.assertEqual(idx, set(LONG.index))
        self.assertEqual(set(r.attritionnel.index) & set(r.grands.index), set())
        print("    OK T3a partition exacte : attritionnel ⊎ grands = source")

    def test_montants_conserves(self):
        r = separer_par_seuil(LONG, 1000.)
        self.assertAlmostEqual(r.montant_grands + r.montant_attritionnel,
                               float(LONG['montant_paye'].sum()), places=6)
        print("    OK T3b montants conservés (grands + attritionnel = total)")

    def _chainer(self, source, seuil):
        """Le CONTRAT DE LA FAÇADE (module 7), exécuté ici : le repère de la
        SOURCE COMPLÈTE est passé aux DEUX constructions, si bien que les deux
        triangles partagent années et zone connue."""
        t_total = construire_triangles(paiements=source)
        repere = (t_total.annee_min, *t_total.paiements.shape)
        r = separer_par_seuil(source, seuil)
        t_att = construire_triangles(paiements=r.attritionnel,
                                     annees_reference=repere)
        t_gra = construire_triangles(paiements=r.grands, annees_reference=repere)
        return r, t_total, t_att, t_gra

    def test_chainage_plusieurs_gros_sinistres(self):
        """(3) Contrôle : plusieurs gros sinistres répartis normalement."""
        r, t_tot, t_att, t_gra = self._chainer(LONG, 1000.)
        self.assertEqual(len(r.sinistres_grands), 2)                  # S1 et S3
        for t in (t_att, t_gra):
            self.assertEqual(t.paiements.shape, t_tot.paiements.shape)
            self.assertEqual(t.annee_min, t_tot.annee_min)
        np.testing.assert_allclose(t_att.paiements + t_gra.paiements,
                                   t_tot.paiements, rtol=1e-9, atol=1e-9)
        print("    OK T3c chaînage (plusieurs gros) : C_attrit + C_grands = C_total")

    def test_chainage_un_seul_gros_sinistre(self):
        """(1) UN SEUL gros sinistre : triangle presque vide mais correctement
        positionné sur le repère, chaînage exact."""
        r, t_tot, t_att, t_gra = self._chainer(LONG, 1500.)           # seul S3 = 2000
        self.assertEqual(len(r.sinistres_grands), 1)
        self.assertEqual(t_gra.paiements.shape, t_tot.paiements.shape)
        # le 2000 est sur 2022 (ligne 2), les autres années à zéro
        self.assertAlmostEqual(t_gra.paiements[2, 0], 2000.0, places=2)
        self.assertAlmostEqual(float(t_gra.paiements[0].sum()), 0.0, places=2)
        np.testing.assert_allclose(t_att.paiements + t_gra.paiements,
                                   t_tot.paiements, rtol=1e-9, atol=1e-9)
        print("    OK T3e un seul gros : bien positionné (2000 sur 2022), chaînage exact")

    def test_chainage_zero_gros_sinistre(self):
        """(2) ZÉRO gros sinistre : triangle de zéros sur le repère, PAS
        d'exception — cas nominal (un seuil qui ne capture personne est normal)."""
        r, t_tot, t_att, t_gra = self._chainer(LONG, 1e9)
        self.assertEqual(r.n_grands, 0)
        self.assertEqual(t_gra.paiements.shape, t_tot.paiements.shape)
        self.assertAlmostEqual(float(t_gra.paiements.sum()), 0.0, places=2)
        np.testing.assert_allclose(t_att.paiements, t_tot.paiements,
                                   rtol=1e-9, atol=1e-9)
        print("    OK T3f zéro gros : triangle de zéros, aucune exception, chaînage exact")

    def test_attritionnel_garde_toutes_les_annees(self):
        """(4) LE cas qui a déclenché l'investigation : les gros sinistres sont
        concentrés sur certaines années. Sans repère imposé, l'attritionnel
        PERDAIT les années où il n'a aucun petit sinistre."""
        r, t_tot, t_att, t_gra = self._chainer(LONG, 1000.)
        # l'attritionnel ne contient QUE 2021 (S2), mais son triangle a 3 années
        self.assertEqual(set(r.attritionnel['annee_survenance']), {2021})
        self.assertEqual(t_att.paiements.shape[0], 3)
        self.assertEqual(t_att.annee_min, 2020)
        self.assertAlmostEqual(float(t_att.paiements[0].sum()), 0.0, places=2)  # 2020
        self.assertAlmostEqual(t_att.paiements[1, 0], 100.0, places=2)          # 2021
        # preuve du défaut d'origine : SANS repère, une seule ligne
        sans_repere = construire_triangles(paiements=r.attritionnel)
        self.assertEqual(sans_repere.paiements.shape[0], 1)
        self.assertEqual(sans_repere.annee_min, 2021)
        print("    OK T3g attritionnel : 3 années conservées avec repère "
              "(1 seule sans — le défaut d'origine)")

    def test_seuil_sans_effet_et_seuil_trop_bas_alertes(self):
        haut = separer_par_seuil(LONG, 1e9)
        self.assertEqual(haut.n_grands, 0)
        self.assertTrue(any('Aucun sinistre' in a for a in haut.rapport['alertes']))
        bas = separer_par_seuil(LONG, 1.)
        self.assertEqual(bas.n_attritionnels, 0)
        self.assertTrue(any('TOUS les sinistres' in a for a in bas.rapport['alertes']))
        print("    OK T3d seuil trop haut / trop bas : les deux alertés")


class T3b_Avertissement_Volume(unittest.TestCase):
    """Q1 tranchée : on construit TOUJOURS les deux triangles, et on QUALIFIE
    l'usage du triangle grands par un avertissement — jamais une absence d'objet."""

    def test_faible_volume_qualifie_diagnostic(self):
        r = separer_par_seuil(LONG, 1500.)                    # 1 seul dossier
        self.assertIn('DIAGNOSTIC', r.avertissement_volume)
        self.assertIn('1 dossier', r.avertissement_volume)
        self.assertFalse(r.grands.empty)                      # construit quand même
        print("    OK T3h faible volume : qualifié DIAGNOSTIC, triangle construit")

    def test_zero_dossier_qualifie(self):
        r = separer_par_seuil(LONG, 1e9)
        self.assertIn('Aucun dossier', r.avertissement_volume)
        print("    OK T3i zéro dossier : avertissement dédié")

    def test_avertissement_toujours_renseigne(self):
        """Le champ n'est JAMAIS vide ni nul : il qualifie, il ne conditionne pas."""
        for seuil in (1., 1000., 1500., 1e9):
            r = separer_par_seuil(LONG, seuil)
            self.assertIsInstance(r.avertissement_volume, str)
            self.assertNotEqual(r.avertissement_volume.strip(), '')
        print("    OK T3j avertissement toujours renseigné (aucun champ conditionnel)")


class T4_Garde_Fous(unittest.TestCase):
    """Le triangle déjà agrégé, à deux niveaux."""

    def test_matrice_leve(self):
        with self.assertRaises(SeparationImpossible) as ctx:
            separer_par_seuil(MATRICE, 1000.)
        self.assertIn('somme', str(ctx.exception))
        print("    OK T4a matrice agrégée → SeparationImpossible")

    def test_avertir_sans_lever(self):
        """La façade doit pouvoir avertir-et-poursuivre sans faire tomber le run."""
        self.assertIsNotNone(avertir_si_agregat(MATRICE))
        self.assertIsNotNone(avertir_si_agregat(pd.DataFrame({'dev0': [1.]})))
        self.assertIsNone(avertir_si_agregat(LONG))          # table longue : OK
        print("    OK T4b avertir_si_agregat : message sans lever, None si longue")

    def test_seuil_invalide_leve(self):
        for mauvais in (0., -100., float('nan'), float('inf')):
            with self.assertRaises(SeparationImpossible, msg=str(mauvais)):
                separer_par_seuil(LONG, mauvais)
        print("    OK T4c seuil ≤ 0 / NaN / inf → lève")


class T5_Verrou_De_Perimetre(unittest.TestCase):
    """Ce module IDENTIFIE et ISOLE — il ne chiffre JAMAIS de réserve."""

    def test_aucun_champ_de_reserve_dans_la_sortie(self):
        """Verrou explicite : aucun champ du résultat ne doit ressembler à une
        réserve. Si quelqu'un ajoutait un jour `reserve_grands_sinistres` à la
        dataclass, ce test deviendrait rouge — c'est tout son intérêt."""
        r = separer_par_seuil(LONG, 1000.)
        champs = {f.name for f in dataclasses.fields(SeparationLLT)}
        interdits = {'reserve', 'ibnr', 'ultime', 'ultimate', 'best_estimate', 'be'}
        for champ in champs:
            mots = set(champ.lower().split('_'))
            self.assertFalse(mots & interdits,
                             f"champ '{champ}' évoque une réserve — hors périmètre")
        # et la synthèse non plus
        for cle in r.synthese():
            mots = set(cle.lower().split('_'))
            self.assertFalse(mots & interdits, f"clé de synthèse '{cle}' interdite")
        print(f"    OK T5a verrou de périmètre : aucun champ de réserve ({len(champs)} champs)")

    def test_sortie_est_bien_des_tables_longues(self):
        """Le module 4 reste le SEUL agrégateur : la sortie n'est pas un triangle."""
        r = separer_par_seuil(LONG, 1000.)
        self.assertIsInstance(r.attritionnel, pd.DataFrame)
        self.assertIsInstance(r.grands, pd.DataFrame)
        self.assertIn('annee_survenance', r.attritionnel.columns)
        print("    OK T5b sortie = tables longues (pas de triangle construit ici)")

    def test_synthese_json_serialisable(self):
        r = separer_par_seuil(LONG, 1000.)
        s = r.synthese()
        json.dumps(s)
        for cle in ('seuil_llt', 'n_grands', 'base_classement_utilisee',
                    'classement_par_sinistre', 'sinistres_grands'):
            self.assertIn(cle, s)
        self.assertEqual(len(s['sinistres_grands']), 2)
        print("    OK T5c synthese() sérialisable, liste des grands incluse")


if __name__ == '__main__':
    unittest.main()
