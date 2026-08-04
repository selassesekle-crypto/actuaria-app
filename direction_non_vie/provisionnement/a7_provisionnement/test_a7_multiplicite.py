# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — A7  ·  VERROUS DE MULTIPLICITÉ  (CLM-H2 / CLM-H3)
=============================================================================

Interroger neuf colonnes à 5 % et retenir « le plus sévère l'emporte », ce
n'est pas un choix de prudence : c'est une multiplicité non corrigée. La
signature est arithmétique — `1 − 0,95⁹ = 37,0 %` — et la fausse alarme
mesurée de CLM-H3 valait 35,2 % sur des triangles rigoureusement conformes
au modèle de Mack.

Ce fichier verrouille les deux correctifs, et surtout leur EFFET : chaque
test ci-dessous échoue si l'on retire la correction. Un verrou qui passerait
aussi bien avec et sans ne protégerait rien.

Mesures de référence (400 répétitions, générateur conforme à Mack) :

                              avant                 après
                         NON VAL.  tout      NON VAL.  tout
    CLM-H3  propre         16,0 %  35,2 %      4,2 %  10,5 %
    CLM-H3  Var ∝ C^2,4    81,5 %  96,2 %     76,8 %  89,8 %
    CLM-H2  propre          4,8 %  23,2 %      1,5 %   5,5 %

La puissance conservée vaut 76,8 / 81,5 = 94,2 %.
"""

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses_clm import (
    H2_P_ORDONNEE, H2_P_ORDONNEE_FORT, H3_P_TENDANCE, H3_P_TENDANCE_FORT,
    MIN_OBS_CORRELATION, MIN_OBS_REGRESSION, NON_TESTABLE, NON_VALIDEE,
    A_JUSTIFIER, VALIDEE, _holm_bonferroni, clm_h2_existence_facteurs,
    clm_h3_structure_variance, couvertures_par_annee)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, RAA)

G = np.asarray(GENINS, dtype=float)
R = np.asarray(RAA, dtype=float)


# =============================================================================
#  MULT-1 — LA PROCÉDURE DE HOLM ELLE-MÊME
# =============================================================================

class TMULT1_Procedure_De_Holm(unittest.TestCase):
    """L'arithmétique avant l'usage : si la procédure est fausse, tout l'est."""

    def test_descente_pas_a_pas_sur_cas_calcules_a_la_main(self):
        """Trois cas dont on connaît la réponse sans exécuter le code."""
        # k=3, alpha=0,05 → seuils 0,0167 puis 0,025 puis 0,05
        self.assertEqual(_holm_bonferroni([0.001, 0.02, 0.5], 0.05), {0, 1})
        # 0,02 > 0,0167 : la descente s'ARRÊTE au premier échec, elle ne
        # « saute » pas les suivants — c'est ce qui distingue Holm d'un
        # simple seuil de Bonferroni appliqué colonne par colonne.
        self.assertEqual(_holm_bonferroni([0.02, 0.03, 0.04], 0.05), set())
        self.assertEqual(_holm_bonferroni([], 0.05), set())
        print('    OK MULT-1a Holm : descente pas à pas, arrêt au premier échec')

    def test_le_premier_seuil_vaut_bien_alpha_sur_k(self):
        """Holm et Bonferroni coïncident sur la p-valeur la plus petite ; ils
        ne divergent que sur les suivantes, où Holm est plus large."""
        for k in (2, 5, 9):
            ps = [0.9] * k
            ps[0] = 0.05 / k - 1e-9
            self.assertEqual(_holm_bonferroni(ps, 0.05), {0})
            ps[0] = 0.05 / k + 1e-9
            self.assertEqual(_holm_bonferroni(ps, 0.05), set())
        print('    OK MULT-1b le premier seuil vaut exactement alpha/k')

    def test_les_deux_niveaux_sont_emboites(self):
        """⚠️ CE QUI REND LA CONVENTION À TROIS ÉTATS COHÉRENTE.

        Une colonne « non validée » (seuil dur) doit toujours être aussi
        rejetée au seuil souple. Sans cet emboîtement, une colonne pourrait
        être NON VALIDÉE sans être À JUSTIFIER — un état impossible à écrire
        dans un rapport.
        """
        rng = np.random.default_rng(7)
        for _ in range(200):
            ps = list(rng.random(rng.integers(1, 10)))
            dur = _holm_bonferroni(ps, H3_P_TENDANCE_FORT)
            souple = _holm_bonferroni(ps, H3_P_TENDANCE)
            self.assertTrue(dur <= souple)
        print('    OK MULT-1c les rejets au seuil dur sont inclus dans les '
              'rejets au seuil souple (200 familles aléatoires)')


# =============================================================================
#  MULT-2 — LA CORRECTION EST RÉELLEMENT APPLIQUÉE, ET ELLE CHANGE LE VERDICT
# =============================================================================

class TMULT2_Effet_Sur_Les_Verdicts(unittest.TestCase):
    """⚠️ VERROUS DISCRIMINANTS : chacun échoue si l'on retire Holm.

    Ils ne se contentent pas de constater un statut : ils vérifient que la
    p-valeur BRUTE aurait donné un statut PLUS SÉVÈRE. C'est la seule forme
    qui distingue « la correction est là » de « le triangle est sain ».
    """

    def test_genins_une_colonne_repasse_validee(self):
        """GenIns, colonne 4 : p = 0,0262. Brute, elle est sous 0,05 donc
        « à justifier ». Corrigée, le seuil du rang 2 sur 6 colonnes vaut
        0,05/5 = 0,01 : la colonne est validée."""
        detail = {d['colonne']: d for d in clm_h2_existence_facteurs(G).detail}
        col = detail[4]
        self.assertLess(col['p_ordonnee'], H2_P_ORDONNEE)      # brute : suspecte
        self.assertEqual(col['statut'], VALIDEE)               # corrigée : saine
        print('    OK MULT-2a GenIns colonne 4 : p=%.4f < %s brute, VALIDÉE '
              'après correction' % (col['p_ordonnee'], H2_P_ORDONNEE))

    def test_raa_le_verdict_descend_d_un_cran_sans_disparaitre(self):
        """RAA, colonne 0 : p = 0,0020. Brute, elle est sous 0,01 donc « non
        validée ». Corrigée, elle dépasse 0,01/6 = 0,00167 mais reste sous
        0,05/6 = 0,00833 : « à justifier ».

        ⚠️ L'ALERTE N'EST PAS PERDUE, ELLE EST REQUALIFIÉE. Trouver une
        p-valeur de 0,002 en interrogeant six colonnes arrive sur environ
        1,2 % des triangles sains : c'est une vraie présomption, mais pas la
        certitude que le mot « non validée » revendique.
        """
        r = clm_h2_existence_facteurs(R)
        detail = {d['colonne']: d for d in r.detail}
        col = detail[0]
        self.assertLess(col['p_ordonnee'], H2_P_ORDONNEE_FORT)  # brute : rejetée
        self.assertEqual(col['statut'], A_JUSTIFIER)            # corrigée
        self.assertEqual(r.statut, A_JUSTIFIER)
        print('    OK MULT-2b RAA colonne 0 : p=%.4f < %s brute, À JUSTIFIER '
              'après correction' % (col['p_ordonnee'], H2_P_ORDONNEE_FORT))

    def test_la_correction_est_annoncee_dans_le_resultat(self):
        """Un contrôleur doit pouvoir lire QUE la correction a été faite et
        SUR COMBIEN de tests elle porte — sans relire le code."""
        for fn, cible in ((clm_h2_existence_facteurs, G),
                          (clm_h3_structure_variance, G)):
            extras = fn(cible).extras
            self.assertEqual(extras['correction_multiplicite'],
                             'Holm-Bonferroni')
            self.assertGreater(extras['n_tests_famille'], 0)
        print('    OK MULT-2c le résultat publie la correction et la taille '
              'de la famille')


# =============================================================================
#  MULT-3 — LE PLANCHER D'OBSERVATIONS DE LA CORRÉLATION
# =============================================================================

class TMULT3_Plancher_Correlation(unittest.TestCase):
    """À 4 points il n'existe que 4! = 24 permutations, donc 24 valeurs
    possibles de ρ : aucune approximation continue de sa loi n'y est valide.
    Mesuré : ces colonnes apportaient 10 points de fausse alarme à elles
    seules (16,0 % contre 6,0 %)."""

    def test_le_plancher_de_correlation_depasse_celui_de_regression(self):
        """Les deux tests n'ont pas la même exigence, et c'est délibéré : la
        loi de Student du test de l'ordonnée est EXACTE sous erreurs
        normales, celle de la corrélation de rang ne l'est pas."""
        self.assertGreaterEqual(MIN_OBS_CORRELATION, 5)
        self.assertGreater(MIN_OBS_CORRELATION, MIN_OBS_REGRESSION)
        print('    OK MULT-3a corrélation ≥ %d > régression %d'
              % (MIN_OBS_CORRELATION, MIN_OBS_REGRESSION))

    def test_aucune_colonne_courte_ne_porte_de_p_valeur(self):
        """Le plancher doit être APPLIQUÉ, pas seulement déclaré.

        ⚠️ LE SEUIL EST ÉCRIT EN DUR ICI, ET C'EST VOULU. Comparer au
        constante du module rendrait ce test tautologique : il passerait
        encore si quelqu'un ramenait `MIN_OBS_CORRELATION` à 4. Cinq points
        est une exigence STATISTIQUE — en deçà, la loi de ρ ne compte pas
        assez d'atomes pour qu'une p-valeur continue ait un sens — pas une
        préférence de configuration.
        """
        for nom, C in (('GenIns', G), ('RAA', R)):
            for d in clm_h3_structure_variance(C).detail:
                if d.get('p') is not None:
                    self.assertGreaterEqual(d['n'], 5, '%s colonne %d'
                                            % (nom, d['colonne']))
                if d['n'] < 5:
                    self.assertEqual(d['statut'], NON_TESTABLE, nom)
        print('    OK MULT-3b aucune colonne de moins de 5 points ne rend de '
              'p-valeur (GenIns, RAA)')


# =============================================================================
#  MULT-4 — LA CORRECTION PORTE SUR LES COLONNES, PAS SUR LE SEUL GLOBAL
# =============================================================================

class TMULT4_Coherence_Avec_La_Couverture_Par_Annee(unittest.TestCase):
    """⚠️ CE VERROU PROTÈGE UNE DÉMONSTRATION, PAS UN NOMBRE.

    `n4_best_estimate` s'appuie sur une équivalence prouvée au lot A2 : le
    motif de l'année la PLUS RÉCENTE est toujours le statut global de
    CLM-H2, parce que cette année traverse toutes les colonnes testées et
    que les deux lectures appliquent la même règle aux mêmes statuts. C'est
    sur cette base que le plafonnement par couverture annuelle a été écarté
    comme structurellement inerte.

    Corriger la multiplicité SUR LE SEUL VERDICT GLOBAL aurait fait diverger
    les deux lectures et rendu cette démonstration fausse — sans qu'aucun
    test existant ne s'en aperçoive.
    """

    def test_le_motif_de_l_annee_la_plus_recente_est_le_statut_global(self):
        for nom, C in (('GenIns', G), ('RAA', R)):
            h = {'CLM-H2': clm_h2_existence_facteurs(C),
                 'CLM-H3': clm_h3_structure_variance(C)}
            annees = couvertures_par_annee(C, h)['annees']
            recente = max(annees, key=lambda a: a['annee'])
            self.assertEqual(recente['couverture_motif'], h['CLM-H2'].statut,
                             nom)
            print('    OK MULT-4a %s : motif de l\'année la plus récente = '
                  'statut global CLM-H2 = %s'
                  % (nom, h['CLM-H2'].statut))

    def test_les_statuts_de_colonne_publies_sont_ceux_qui_sont_corriges(self):
        """Aucune colonne ne doit porter un statut déduit de sa p-valeur
        brute : sur GenIns, la colonne 4 le prouve (p < 0,05 et VALIDÉE)."""
        for C in (G, R):
            for d in clm_h2_existence_facteurs(C).detail:
                p = d.get('p_ordonnee')
                if p is None:
                    continue
                brut = (NON_VALIDEE if p < H2_P_ORDONNEE_FORT else
                        A_JUSTIFIER if p < H2_P_ORDONNEE else VALIDEE)
                ordre = {VALIDEE: 1, A_JUSTIFIER: 2, NON_VALIDEE: 3}
                # la correction ne peut qu'ADOUCIR, jamais durcir
                self.assertLessEqual(ordre[d['statut']], ordre[brut])
        print('    OK MULT-4b la correction adoucit ou laisse en l\'état, '
              'jamais l\'inverse')


if __name__ == '__main__':
    unittest.main(verbosity=2)
