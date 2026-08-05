# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — A7  ·  VERROUS DE LA PUISSANCE PUBLIÉE  (P2 — BFCC-H5, MCL-H2)
=============================================================================

Deux générateurs de plus, chacun pour la nulle de SON hypothèse :

  BFCC-H5  nulle = un loss ratio SANS tendance     violer : une pente en pts/an
  MCL-H2   nulle = une réponse LINÉAIRE (Quarg &   violer : un terme quadratique
           Mack)

⚠️ LE TÉMOIN COMMANDE TOUT, ET P2 L'A REVÉRIFIÉ À SES DÉPENS. Le générateur
de Munich employait d'abord un λ codé en dur à 0,35, là où la paire réelle en
porte −0,0 : le témoin passait de 7,5 % à 17,5 %, et toute puissance qu'il
aurait produite aurait été fausse. Le λ vient désormais DES DONNÉES.

⚠️ CE QUE P2 NE LIVRE PAS, ET POURQUOI. Le générateur ODP de BOOT-H3 a été
écrit et sa mesure a révélé autre chose : soumis à des triangles tirés de SA
PROPRE nulle, à son réglage de production (400 régénérations), BOOT-H3 rejette
21 à 30 % des cas — quatre mesures, deux triangles, deux graines, 100
simulations chacune — pour un nominal de 10 %. Publier « ce test détecterait
X % » à côté d'un test dans cet état serait exactement le chiffre faux que la
règle interdit. Le constat appelle un lot à lui seul.
"""

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses_bfcc import (
    H5_DERIVE_PUBLIEE, lignes_hypotheses_bfcc, puissance_bfcc,
    verifier_hypotheses_bfcc)
from direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses_munich import (
    MCL_H2_COURBURE_PUBLIEE, lignes_hypotheses_munich, puissance_munich,
    verifier_hypotheses_munich)
from direction_non_vie.provisionnement.a7_provisionnement.n2_puissance import (
    GRAINE_PUISSANCE, N_SIM_PUISSANCE, lambda_paye, regenerer_loss_ratio,
    regenerer_munich)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, RAA,
)

_G = np.asarray(GENINS, dtype=float)
_R = np.asarray(RAA, dtype=float)


def _engage(C, coef=0.15):
    """Engagés plausibles : croissants et supérieurs au payé en toute cellule."""
    C = np.asarray(C, dtype=float)
    n = C.shape[0]
    E = np.zeros_like(C)
    for i in range(n):
        for j in range(n - i):
            E[i, j] = C[i, j] * (1.0 + coef * (1.0 - j / (n - 1.0)))
    return E


def _entrees_lr(C):
    """Ultimes et exposition, du même ordre de grandeur que le triangle."""
    n = C.shape[0]
    ultimes = [C[i, n - i - 1] * 1.15 for i in range(n)]
    expo = [float(np.nanmean(C[:, 0])) * 8.0] * n
    return ultimes, expo


# =============================================================================
#  P2-1 — LES TÉMOINS
# =============================================================================

class TP2_1_Temoins(unittest.TestCase):
    """⚠️ À LIRE EN PREMIER. Si ces tests tombent, aucune puissance publiée
    par les deux générateurs de P2 n'a de valeur."""

    def test_temoin_du_generateur_loss_ratio(self):
        for nom, C in (('GenIns', _G), ('RAA', _R)):
            ultimes, expo = _entrees_lr(C)
            t = puissance_bfcc(ultimes, expo, None)['BFCC-H5']['temoin']
            self.assertIsNotNone(t, nom)
            self.assertLessEqual(
                t, 25,
                f"{nom} : témoin de {t} % — le générateur de loss ratio ne "
                f"respecte pas la nulle de BFCC-H5")
        print("    OK P2-1a témoin du générateur loss ratio ≤ 25 % sur les "
              "deux triangles de référence")

    def test_temoin_du_generateur_munich(self):
        for nom, C in (('GenIns', _G), ('RAA', _R)):
            t = puissance_munich(C, _engage(C))['MCL-H2']['temoin']
            self.assertIsNotNone(t, nom)
            self.assertLessEqual(
                t, 25,
                f"{nom} : témoin de {t} % — le générateur de Munich ne "
                f"respecte pas la nulle de MCL-H2")
        print("    OK P2-1b témoin du générateur Munich ≤ 25 % sur les deux "
              "triangles de référence")

    def test_le_lambda_vient_des_donnees(self):
        """⚠️ LA LEÇON DE P2, VERROUILLÉE. Coder λ = 0,35 « par défaut » là où
        la paire en porte −0,0 faisait passer le témoin de 7,5 % à 17,5 %."""
        lam = lambda_paye(_G, _engage(_G))
        self.assertIsNotNone(lam)
        self.assertLess(abs(lam), 1.0, "λ hors de toute plage plausible")
        # Deux paires différentes doivent donner deux λ différents : si la
        # fonction rendait une constante, ce test le verrait.
        lam2 = lambda_paye(_G, _engage(_G, coef=0.60))
        self.assertNotEqual(round(lam, 6), round(lam2, 6))
        print(f"    OK P2-1c λ estimé sur les données : {lam:+.4f} sur une "
              f"paire, {lam2:+.4f} sur une autre — jamais une constante")

    def test_chaque_violation_mord(self):
        rng = np.random.default_rng(1)
        ultimes, expo = _entrees_lr(_G)
        a = regenerer_loss_ratio(np.asarray(ultimes), np.asarray(expo),
                                 np.random.default_rng(1))
        b = regenerer_loss_ratio(np.asarray(ultimes), np.asarray(expo),
                                 np.random.default_rng(1), pente=0.05)
        self.assertFalse(np.allclose(a, b), "la pente de loss ratio ne mord pas")
        lam = lambda_paye(_G, _engage(_G))
        p1 = regenerer_munich(_G, _engage(_G), lam, np.random.default_rng(1))
        p2 = regenerer_munich(_G, _engage(_G), lam, np.random.default_rng(1),
                              quad=0.5)
        self.assertFalse(np.allclose(p1[0], p2[0]),
                         "la courbure de Munich ne mord pas")
        del rng
        print("    OK P2-1d les deux violations modifient effectivement le "
              "jeu régénéré")


# =============================================================================
#  P2-2 — CE QUI EST PUBLIÉ
# =============================================================================

class TP2_2_Publication(unittest.TestCase):

    def test_reproductible(self):
        ultimes, expo = _entrees_lr(_G)
        a = puissance_bfcc(ultimes, expo, None)['BFCC-H5']
        b = puissance_bfcc(ultimes, expo, None)['BFCC-H5']
        self.assertEqual(a['puissance'], b['puissance'])
        self.assertEqual(a['graine'], GRAINE_PUISSANCE)
        self.assertEqual(a['n_simulations'], N_SIM_PUISSANCE)
        c = puissance_munich(_G, _engage(_G))['MCL-H2']
        d = puissance_munich(_G, _engage(_G))['MCL-H2']
        self.assertEqual(c['puissance'], d['puissance'])
        print("    OK P2-2a les deux puissances sont reproductibles à graine "
              "fixe")

    def test_les_neuf_autres_disent_sans_objet(self):
        """⚠️ NE JAMAIS INVENTER UN CHIFFRE. Neuf des onze hypothèses de ces
        deux familles ne sont pas des tests statistiques, ou reprennent un
        verdict testé ailleurs."""
        p = puissance_bfcc(*_entrees_lr(_G), None)
        p.update(puissance_munich(_G, _engage(_G)))
        sans = [c for c, e in p.items() if not e.get('mesurable')]
        self.assertEqual(len(sans), 9, sorted(sans))
        for code in sans:
            self.assertNotIn('puissance', p[code])
            self.assertIn("n'y a pas de sens", p[code]['phrase'])
        print(f"    OK P2-2b {len(sans)} hypothèses déclarées sans objet, "
              f"aucun chiffre inventé")

    def test_la_puissance_suit_l_ampleur(self):
        """Une violation plus forte doit être plus souvent détectée."""
        from direction_non_vie.provisionnement.a7_provisionnement \
            .n2_hypotheses_bfcc import bfcc_h5_stabilite_lr
        ultimes, expo = _entrees_lr(_G)
        u = np.asarray(ultimes); e = np.asarray(expo)

        def taux(pente):
            rng = np.random.default_rng(GRAINE_PUISSANCE)
            k = 0
            for _ in range(N_SIM_PUISSANCE):
                sim = regenerer_loss_ratio(u, e, rng, pente=pente)
                if str(bfcc_h5_stabilite_lr(sim, e, [True] * len(u)).statut) \
                        not in ('VALIDÉE', 'NON TESTABLE'):
                    k += 1
            return 100.0 * k / N_SIM_PUISSANCE

        faible, forte = taux(0.02), taux(0.20)
        self.assertGreater(forte, faible)
        print(f"    OK P2-2c BFCC-H5 : 2 pts/an → {faible:.0f} %, "
              f"20 pts/an → {forte:.0f} % — la puissance suit l'ampleur")

    def test_les_ampleurs_publiees_sont_dans_les_unites_du_metier(self):
        """Une puissance sans l'ampleur à laquelle elle se rapporte ne veut
        rien dire — et l'ampleur doit se lire sans dictionnaire."""
        self.assertAlmostEqual(H5_DERIVE_PUBLIEE, 0.03, places=6)
        self.assertGreater(MCL_H2_COURBURE_PUBLIEE, 0.0)
        p = puissance_bfcc(*_entrees_lr(_G), None)['BFCC-H5']
        self.assertIn('points de loss ratio par an', p['effet'])
        print(f"    OK P2-2d BFCC-H5 s'exprime en points de loss ratio par an "
              f"({H5_DERIVE_PUBLIEE * 100:.0f} pts)")


# =============================================================================
#  P2-3 — L'ARRIVÉE DANS LES LIVRABLES
# =============================================================================

class TP2_3_Livrables(unittest.TestCase):

    def test_les_lignes_bfcc_portent_la_puissance(self):
        ultimes, expo = _entrees_lr(_G)
        n = len(ultimes)
        # ⚠️ Les quatre séquences doivent avoir la MÊME longueur : `cadence_ok`
        # indexe les années d'origine comme `ultimates_cl`.
        n2 = {'bfcc': verifier_hypotheses_bfcc(
            pct_brut=[1.0 / n] * n, cadence_ok=[True] * n,
            bf={}, cape_cod={}, ultimates_cl=ultimes, exposition=expo)}
        par_code = {x['code']: x for x in lignes_hypotheses_bfcc(n2)}
        self.assertIsNotNone(par_code['BFCC-H5']['puissance'])
        self.assertIn('détecterait', par_code['BFCC-H5']['puissance_phrase'])
        self.assertIn("n'y a pas de sens",
                      par_code['BFCC-H2']['puissance_phrase'])
        print("    OK P2-3a les lignes BFCC portent la puissance de H5 et la "
              "mention de non-pertinence des autres")

    def test_les_lignes_munich_portent_la_puissance(self):
        n2 = {'munich_hyp': verifier_hypotheses_munich(_G, _engage(_G))}
        par_code = {x['code']: x for x in lignes_hypotheses_munich(n2)}
        self.assertIsNotNone(par_code['MCL-H2']['puissance'])
        self.assertIn('détecterait', par_code['MCL-H2']['puissance_phrase'])
        self.assertIn("n'y a pas de sens",
                      par_code['MCL-H4']['puissance_phrase'])
        print("    OK P2-3b les lignes Munich portent la puissance de H2 et la "
              "mention de non-pertinence des autres")

    def test_une_ligne_sans_puissance_calculee_n_en_affiche_pas(self):
        """Le faux zéro, verrouillé des deux côtés comme il l'est pour CLM."""
        for lignes in (lignes_hypotheses_bfcc({'bfcc': {}}),
                       lignes_hypotheses_munich({'munich_hyp': {}})):
            for x in lignes:
                self.assertEqual(x['puissance_phrase'], '')
                self.assertIsNone(x['puissance'])
        print("    OK P2-3c sans puissance calculée, aucune phrase n'est "
              "affichée — ni tiret, ni zéro")


if __name__ == '__main__':
    unittest.main(verbosity=2)
