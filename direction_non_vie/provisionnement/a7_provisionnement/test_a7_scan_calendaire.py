# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — A7  ·  VERROUS DU TEST DE SCAN CALENDAIRE  (CLM-H1)
=============================================================================

CLM-H1 s'appuie désormais sur DEUX tests, et la complémentarité est
mathématique, pas décorative :

  · le test des SIGNES du guide (annexe 9.d.i) lit les FACTEURS BRUTS. Il ne
    retient que le signe des écarts, jamais leur amplitude — il sature, et
    plafonne à 37 % de détection sur un choc, quelle qu'en soit la taille.
    Mais il voit les DÉRIVES PROGRESSIVES.
  · le test de SCAN lit les RÉSIDUS d'un ajustement chain-ladder, retient
    l'amplitude et la concentre sur la diagonale la plus écartée. Il atteint
    100 % sur un choc ×2. Mais ce que l'ajustement ABSORBE ne laisse rien
    dans ses résidus : une dérive progressive lui échappe par construction.

MESURÉ, 120 à 200 répétitions, triangles 10×10 :

                                   signes    scan
    fausse alarme                   10,4 %    6,0 %
    choc ×2,00 sur 1 diagonale      36,7 %  100,0 %
    choc ×2,00 sur 5 diagonales     34,2 %   73,0 %
    dérive progressive 1,5 %        31,7 %    8,5 %   ← l'angle mort du scan

Le scan décide le statut ; le verdict du guide est publié et NOMMÉ dans le
message dès qu'il est plus sévère. Ces verrous protègent les deux moitiés.
"""

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses_clm import (
    A_JUSTIFIER, NON_TESTABLE, NON_VALIDEE, SCAN_GRAINE, SCAN_MIN_DIAGONALES,
    SCAN_N_PERMUTATIONS, VALIDEE, clm_h1_effet_calendaire, scan_diagonales)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS,
)

_FACTEURS = (3.49, 1.75, 1.46, 1.17, 1.10, 1.05, 1.03, 1.02, 1.01, 1.008)


def triangle(n=10, sigma=140.0, graine=0, choc=None, largeur=1, derive=0.0):
    """Triangle conforme au modèle de Mack, avec effet calendaire optionnel.

    `choc` s'applique aux INCRÉMENTS de `largeur` diagonales consécutives —
    un effet calendaire est un supplément de règlements PAYÉS cette année-là,
    il ne touche donc qu'une diagonale, pas tout ce qui suit.
    """
    rng = np.random.default_rng(graine)
    inc = np.zeros((n, n))
    for i in range(n):
        prev = 1_000_000.0 * 1.05 ** i
        inc[i, 0] = prev
        for j in range(1, n):
            f = _FACTEURS[j - 1] if j - 1 < len(_FACTEURS) else 1.005
            inc[i, j] = max(prev * (f - 1.0) + sigma * np.sqrt(max(prev, 1.0))
                            * rng.standard_normal(), prev * 1e-4)
            prev += inc[i, j]
    if derive:
        for i in range(n):
            for j in range(n):
                inc[i, j] *= (1.0 + derive * (i + j)) ** (i + j)
    if choc is not None:
        d0 = n // 2
        for i in range(n):
            for j in range(n):
                if d0 <= i + j < d0 + largeur:
                    inc[i, j] *= choc
    C = np.cumsum(inc, axis=1)
    for i in range(n):
        for j in range(n - i, n):
            C[i, j] = 0.0
    return C


# =============================================================================
#  SCAN-1 — LE TEST LUI-MÊME
# =============================================================================

class TSCAN1_Le_Test(unittest.TestCase):

    def test_il_designe_la_bonne_annee_calendaire(self):
        """⚠️ CE QUE LE TEST DU GUIDE NE PEUT PAS FAIRE : nommer le coupable.

        Le choc est injecté sur la diagonale `n // 2`. Le scan doit la
        désigner, pas une autre — sans quoi il détecterait « quelque chose »
        sans dire quoi, ce qui n'aiderait pas l'actuaire.
        """
        for n in (10, 12):
            r = scan_diagonales(triangle(n=n, graine=1, choc=2.0))
            self.assertIsNotNone(r)
            self.assertEqual(r['diagonale'], n // 2)
            self.assertGreater(abs(r['ecart']), 3.0)
        print("    OK SCAN-1a le scan désigne la diagonale réellement chargée "
              "(n=10 et n=12), avec un écart > 3 σ")

    def test_la_p_valeur_est_reproductible(self):
        """⚠️ EXIGENCE NON NÉGOCIABLE. Un verdict d'hypothèse qui dépendrait
        d'un tirage non reproductible ne serait pas opposable devant un
        commissaire aux comptes. La graine est fixe et publiée."""
        C = triangle(graine=3, choc=1.6)
        valeurs = {scan_diagonales(C)['p'] for _ in range(3)}
        self.assertEqual(len(valeurs), 1)
        r = clm_h1_effet_calendaire(C)
        self.assertEqual(r.extras['graine'], SCAN_GRAINE)
        self.assertEqual(r.extras['n_permutations'], SCAN_N_PERMUTATIONS)
        print(f"    OK SCAN-1b p-valeur identique sur 3 appels, graine "
              f"{SCAN_GRAINE} et {SCAN_N_PERMUTATIONS} permutations publiées")

    def test_aucune_p_valeur_nulle(self):
        """Un test par permutation ne peut PAS rendre zéro : l'observé fait
        partie de sa propre référence. D'où le +1 au numérateur et au
        dénominateur — sans quoi on publierait une certitude qu'on n'a pas."""
        r = scan_diagonales(triangle(graine=5, choc=6.0))
        self.assertGreater(r['p'], 0.0)
        self.assertAlmostEqual(r['p'], 1.0 / (SCAN_N_PERMUTATIONS + 1), places=9)
        print(f"    OK SCAN-1c p minimale = 1/{SCAN_N_PERMUTATIONS + 1} = "
              f"{1.0 / (SCAN_N_PERMUTATIONS + 1):.6f}, jamais zéro")


# =============================================================================
#  SCAN-2 — LE GARDE-FOU DE TAILLE, ET LE REPLI SUR LE GUIDE
# =============================================================================

class TSCAN2_Garde_Fou(unittest.TestCase):
    """⚠️ PLANCHER CALIBRÉ, PAS CHOISI. Fausse alarme mesurée sur triangles
    sains : 4×4 → 23,3 % · 5×5 → 11,7 % · 6×6 → 8,3 % · 7×7 → 3,3 %.
    En deçà de 7 années le scan se retire, et le guide décide seul."""

    def test_le_scan_se_retire_sous_le_plancher(self):
        for n in (4, 5, 6):
            self.assertIsNone(scan_diagonales(triangle(n=n, graine=2)),
                              f"le scan ne devrait pas se prononcer en {n}×{n}")
        for n in (7, 8, 10):
            self.assertIsNotNone(scan_diagonales(triangle(n=n, graine=2)),
                                 f"le scan devrait se prononcer en {n}×{n}")
        print(f"    OK SCAN-2a frontière nette à {SCAN_MIN_DIAGONALES + 1} "
              f"années : indisponible en 4/5/6, disponible en 7/8/10")

    def test_sous_le_plancher_le_guide_decide_et_le_dit(self):
        """Le repli ne doit pas être silencieux : le lecteur doit savoir que
        le verdict repose sur un seul des deux tests."""
        r = clm_h1_effet_calendaire(triangle(n=6, graine=2))
        self.assertFalse(r.extras['scan_disponible'])
        self.assertIn('seul test des signes', r.message)
        self.assertEqual(r.statut, r.extras['guide_statut'])
        print("    OK SCAN-2b en 6×6 : le guide décide, et le message le dit")

    def test_triangle_minuscule_reste_non_testable(self):
        """Ni l'un ni l'autre ne peut se prononcer : aucun jugement n'est rendu."""
        r = clm_h1_effet_calendaire(np.array([[100., 150., 170.],
                                              [110., 160., 0.],
                                              [120., 0., 0.]]))
        self.assertEqual(r.statut, NON_TESTABLE)
        print("    OK SCAN-2c triangle 3×3 : NON TESTABLE, aucun jugement rendu")


# =============================================================================
#  SCAN-3 — LES DEUX MOITIÉS, ET LE FAIT QU'AUCUNE N'EST TUE
# =============================================================================

class TSCAN3_Deux_Tests_Complementaires(unittest.TestCase):

    def test_le_guide_est_toujours_publie(self):
        """Traçabilité : le test prescrit par le guide reste calculé et lisible,
        même quand il ne décide pas."""
        r = clm_h1_effet_calendaire(np.asarray(GENINS, dtype=float))
        for cle in ('guide_statut', 'guide_statistique', 'guide_reference',
                    'guide_intervalle'):
            self.assertIn(cle, r.extras)
        self.assertIn('9.d.i', r.extras['guide_reference'])
        self.assertEqual(r.extras['guide_intervalle'], [-1.96, 1.96])
        print(f"    OK SCAN-3a le verdict du guide reste publié : "
              f"{r.extras['guide_statut']} (t = "
              f"{r.extras['guide_statistique']:+.2f})")

    def test_le_scan_voit_le_choc_concentre(self):
        """Là où les signes plafonnent : un choc sur UNE diagonale."""
        r = clm_h1_effet_calendaire(triangle(graine=1, choc=2.0))
        self.assertEqual(r.statut, NON_VALIDEE)
        self.assertLess(r.valeur, 0.01)
        print(f"    OK SCAN-3b choc ×2 sur une diagonale : NON VALIDÉE "
              f"(p = {r.valeur:.4f})")

    def test_la_derive_progressive_reste_couverte_par_le_guide(self):
        """⚠️ LE VERROU QUI PROTÈGE L'ANGLE MORT DU SCAN.

        Une dérive calendaire progressive est absorbée par l'ajustement : le
        scan ne peut pas la voir, et c'est structurel. Le test des signes, lui,
        la voit — il lit les facteurs bruts. Ce verrou exige que ce signal
        SURVIVE dans le résultat publié : si un jour on cessait de calculer le
        test du guide, la moitié de la couverture disparaîtrait en silence.
        """
        vus = 0
        for g in range(12):
            r = clm_h1_effet_calendaire(triangle(graine=g, derive=0.015))
            self.assertIsNotNone(r.extras['guide_statut'])
            if r.extras['guide_statut'] != VALIDEE:
                vus += 1
        self.assertGreater(vus, 0,
                           "sur une dérive progressive, le test du guide doit "
                           "encore parler — c'est sa raison d'être ici")
        print(f"    OK SCAN-3c dérive progressive : le test du guide la "
              f"signale sur {vus}/12 tirages, là où le scan est aveugle")

    def test_le_message_nomme_le_guide_quand_il_est_plus_severe(self):
        """La double lecture doit être ÉCRITE, pas seulement calculée."""
        trouve = False
        for g in range(30):
            r = clm_h1_effet_calendaire(triangle(graine=g, derive=0.015))
            ordre = {NON_TESTABLE: 0, VALIDEE: 1, A_JUSTIFIER: 2,
                     NON_VALIDEE: 3}
            if ordre[r.extras['guide_statut']] > ordre[r.statut]:
                self.assertIn('facteurs bruts', r.message)
                self.assertIn('dérive', r.message.lower())
                self.assertIn('votre examen', r.message)
                trouve = True
                break
        self.assertTrue(trouve, "aucun cas de divergence rencontré : le verrou "
                                "ne prouve rien, il faut revoir le scénario")
        print("    OK SCAN-3d quand le guide est plus sévère, le message le "
              "nomme et explique pourquoi les deux lectures diffèrent")

    def test_le_message_ne_presente_jamais_la_divergence_comme_un_doute(self):
        """⚠️ REGISTRE, ET C'EST UNE EXIGENCE MÉTIER.

        Deux tests complémentaires appliqués sciemment sont une MÉTHODE. Un
        message qui laisserait entendre que l'outil hésite produirait
        l'effet inverse de celui recherché chez un actuaire qui signe.
        """
        interdits = ('contradic', 'incohéren', 'ne sait', 'incertitude',
                     'hésit', '⚠')
        for kw in ({}, {'choc': 2.0}, {'derive': 0.015}, {'choc': 1.4}):
            for g in (0, 1, 2):
                msg = clm_h1_effet_calendaire(triangle(graine=g, **kw)).message
                self.assertTrue(msg.startswith('Deux tests complémentaires'))
                for mot in interdits:
                    self.assertNotIn(mot, msg.lower() if mot != '⚠' else msg)
        print("    OK SCAN-3e aucun message n'emploie un registre d'hésitation "
              "(12 combinaisons vérifiées)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
