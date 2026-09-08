# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — LE TRIANGLE TRONQUÉ (m < n) EST UNE FORME NORMALE, PAS UN DÉFAUT
=============================================================================

 CE QUE CE FICHIER TIENT.

 Un triangle de n années de survenance × m périodes de développement avec
 m < n est la PRATIQUE PROFESSIONNELLE STANDARD des branches longues : on
 garde vingt millésimes et huit ans de développement, on ne garde pas vingt
 ans de développement. Sa zone observable est Σ_i min(m, n−i), qui ne vaut
 n(n+1)/2 que lorsque m ≥ n.

 ⚠️⚠️ DEUX SITES, DEUX MODULES, UNE SEULE CAUSE — l'hypothèse de carré.

 · `n3/clark.py` masquait la zone future par `j > m - 1 - i`, soit
   `i + j > m - 1`, quand tout le reste d'A7 emploie `i + j >= n`. Les deux
   coïncident si n = m. Sur un 14×8, Clark ne voyait que 36 des 84 cellules
   connues — les six années les plus récentes, celles qui portent la réserve,
   étaient effacées — et l'ajustement échouait. Mesuré : ÉCHEC sur 10×8, 12×8,
   14×8, 12×10 et 20×10 ; succès sur les seuls carrés 8×8 et 10×10. Sa
   docstring affirmait pourtant « Cas supportés : n>m (court) ».

 · `services/nv_triangle_diagnostics._ctrl_remplissage` comparait les cellules
   remplies à n(n+1)/2. Sur des triangles SANS UNE SEULE CELLULE MANQUANTE :
   20×8 → AMBRE 62,9 %, 25×8 → AMBRE 52,9 %, 30×8 → ROUGE 45,6 % avec la
   recommandation « fournir les données manquantes avant tout calcul S2 ».
   L'alerte était d'autant plus forte que l'historique était plus long.

 ⚠️ CE FICHIER NE COUVRE PAS LE SENS INVERSE (n < m, plus de colonnes de
 développement que d'années). Celui-là n'est pas un défaut de deux sites :
 le moteur de facteurs lui-même (`chain_ladder`, `i + j + 1 >= n`) rend les
 colonnes surnuméraires inexploitables, et A7 le refuse à la porte d'entrée.

 ⚠️ LA VIOLATION EST PLANTÉE : `T3` rejoue les DEUX formules d'avant et exige
 qu'elles échouent là où les nouvelles passent.
=============================================================================
"""

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.n3.clark import (
    clark_ldf)
from direction_non_vie.services.nv_triangle_diagnostics import (
    _ctrl_remplissage)

#: Cadences incrémentales, huit puis dix périodes de développement.
CAD8 = [0.25, 0.20, 0.16, 0.12, 0.10, 0.08, 0.05, 0.04]
CAD10 = CAD8 + [0.02, 0.02]


def _triangle(n, m, base=100000.0):
    """Triangle CUMULÉ n×m, zone connue ENTIÈREMENT remplie."""
    cad = (CAD8 if m <= 8 else CAD10)[:m]
    C = np.zeros((n, m))
    for i in range(n):
        for j in range(m):
            if i + j < n:
                C[i, j] = base * (1 + 0.02 * i) * sum(cad[:j + 1])
    return C


# =============================================================================
#  T1 — CLARK ABOUTIT SUR LES TRIANGLES TRONQUÉS
# =============================================================================

class T1_Clark_Sur_Tronque(unittest.TestCase):

    def test_clark_aboutit_sur_toutes_les_formes_tronquees(self):
        for n, m in ((10, 8), (12, 8), (14, 8), (12, 10), (20, 10)):
            r = clark_ldf(_triangle(n, m))
            self.assertTrue(
                r.get('success'),
                "Clark échoue sur %d×%d, la forme standard des branches "
                "longues : %s" % (n, m, r.get('erreur')))
            attendu = sum(min(m, n - i) for i in range(n))
            self.assertEqual(
                int(r.get('n_obs', 0)), attendu,
                "Clark n'exploite que %s cellules sur les %d de la zone "
                "connue d'un %d×%d" % (r.get('n_obs'), attendu, n, m))
            print("    OK L3-1 Clark %d×%d : %d cellules, réserve %s"
                  % (n, m, attendu, round(float(r.get('reserve_totale', 0)))))

    def test_aucune_regression_sur_les_carres(self):
        """⚠️ LA CONTRE-ÉPREUVE. Un correctif de forme doit être INERTE là où
        la forme était déjà bonne — sinon il déplace un chiffre publié."""
        for n in (8, 10):
            r = clark_ldf(_triangle(n, n))
            self.assertTrue(r.get('success'), "Clark échoue sur le carré %d×%d" % (n, n))
            self.assertEqual(
                int(r.get('n_obs', 0)), n * (n + 1) // 2,
                "la zone connue d'un carré %d×%d est n(n+1)/2" % (n, n))
            print("    OK L3-2 carré %d×%d : %d cellules, réserve %s (inchangé)"
                  % (n, n, n * (n + 1) // 2, round(float(r.get('reserve_totale', 0)))))


# =============================================================================
#  T2 — C7 N'ACCUSE PLUS UN TRIANGLE COMPLET
# =============================================================================

class T2_C7_Ne_Reclame_Plus_L_Impossible(unittest.TestCase):

    def test_un_triangle_tronque_COMPLET_est_a_cent_pour_cent(self):
        for n, m in ((20, 8), (25, 8), (30, 8), (12, 10), (20, 10)):
            C = _triangle(n, m)
            c7 = _ctrl_remplissage(C, n, m)
            self.assertEqual(
                c7['statut'], 'VERT',
                "C7 accuse un %d×%d dont AUCUNE cellule ne manque : %s"
                % (n, m, c7['message']))
            self.assertIn('100.0%', c7['message'],
                          "C7 sur un %d×%d complet : %s" % (n, m, c7['message']))
            print("    OK L3-3 C7 %d×%d complet : VERT 100,0 %%" % (n, m))

    def test_c7_reste_inchange_sur_un_carre(self):
        for n in (8, 10):
            c7 = _ctrl_remplissage(_triangle(n, n), n, n)
            self.assertEqual(c7['statut'], 'VERT')
            self.assertEqual(c7['points'], 10)
            print("    OK L3-4 C7 carré %d×%d : VERT 10/10 (inchangé)" % (n, n))

    def test_c7_voit_encore_un_VRAI_trou(self):
        """⚠️ L'ASSIETTE NE DOIT PAS AVOIR TROP MAIGRI. Un contrôle qui ne
        rougit plus jamais ne protège plus rien : on lui retire de vraies
        cellules et on exige qu'il le voie."""
        n, m = 20, 8
        C = _triangle(n, m)
        for i in range(n):
            for j in range(m):
                if i + j < n and (i + j) % 2 == 0:
                    C[i, j] = 0.0
        c7 = _ctrl_remplissage(C, n, m)
        self.assertIn(c7['statut'], ('AMBRE', 'ROUGE'),
                      "la moitié des cellules retirée et C7 reste VERT : %s"
                      % c7['message'])
        print("    OK L3-5 C7 voit encore un vrai trou : %s" % c7['statut'])


# =============================================================================
#  T3 — LA VIOLATION PLANTÉE : les deux formules d'avant échouent-elles ?
# =============================================================================

class T3_Les_Formules_D_Avant_Echouent(unittest.TestCase):

    def test_le_masque_carre_de_clark_perdait_les_annees_recentes(self):
        n, m = 14, 8
        vue_avant = sum(1 for i in range(n) for j in range(m) if not j > m - 1 - i)
        vue_apres = sum(1 for i in range(n) for j in range(m) if not i + j >= n)
        reelle = sum(min(m, n - i) for i in range(n))
        self.assertEqual(vue_apres, reelle)
        self.assertLess(
            vue_avant, reelle,
            "la formule d'avant ne perdait rien : le test ne prouve rien")
        lignes_perdues = [i for i in range(n)
                          if all(j > m - 1 - i for j in range(m) if i + j < n)]
        self.assertTrue(lignes_perdues,
                        "aucune année entièrement effacée : le plant est mort")
        print("    OK L3-6 plant Clark 14×8 : %d cellules vues au lieu de %d, "
              "années entièrement effacées %s"
              % (vue_avant, reelle, lignes_perdues))

    def test_le_denominateur_carre_accusait_un_triangle_complet(self):
        for n, m, attendu_avant in ((20, 8, 210), (25, 8, 325), (30, 8, 465)):
            avant = n * (n + 1) // 2
            apres = sum(min(m, n - i) for i in range(n))
            self.assertEqual(avant, attendu_avant)
            self.assertLess(
                apres, avant,
                "les deux dénominateurs coïncident sur %d×%d : le plant est "
                "mort" % (n, m))
            rempli = sum(1 for i in range(n) for j in range(m) if i + j < n)
            self.assertEqual(rempli, apres)
            self.assertLess(
                rempli / avant * 100, 80.0,
                "l'ancien dénominateur ne déclenchait pas d'alerte sur "
                "%d×%d : le plant est mort" % (n, m))
            print("    OK L3-7 plant C7 %d×%d : %d/%d = %.1f %% avec l'ancien "
                  "dénominateur, %d/%d = 100,0 %% avec le nouveau"
                  % (n, m, rempli, avant, rempli / avant * 100, rempli, apres))


if __name__ == '__main__':
    unittest.main(verbosity=2)
