# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — A7  ·  VERROUS DE LA PUISSANCE PUBLIÉE  (P1 — CLM-H1/H2/H3)
=============================================================================

Un verdict d'hypothèse dit ce qu'on a trouvé. Il ne dit pas ce qu'on AURAIT
pu trouver. « VALIDÉE » confond donc « j'ai cherché et il n'y a rien » avec
« je n'avais aucun moyen de voir » — deux phrases très différentes devant un
commissaire aux comptes. La puissance publiée tranche entre les deux.

⚠️ LE VERROU QUI COMMANDE TOUS LES AUTRES : LE TÉMOIN.

Un générateur qui ne respecte pas la nulle de l'hypothèse testée produit un
chiffre faux, et un chiffre faux publié est pire que pas de chiffre. L'erreur
a été commise avant d'être corrigée : régénérer depuis l'ajustement ODP donne
à CLM-H2 un témoin de 53 % au lieu de 3 %, parce que l'ODP pose
`E[X_ij] = α_i·β_j` sur les incréments, d'où une relation cumulée d'ordonnée
NON nulle — exactement ce que CLM-H2 rejette.

`TPUIS1` vérifie donc, AVANT tout le reste, que le générateur de Mack rend un
témoin compatible avec le seuil nominal. Si ce test tombe, aucune puissance
publiée par ce module n'a de valeur.
"""

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.n2_hypotheses_clm import (
    NON_TESTABLE, VALIDEE, clm_h1_effet_calendaire, clm_h2_existence_facteurs,
    clm_h3_structure_variance, lignes_hypotheses_clm, puissance_clm,
    verifier_hypotheses_clm)
from direction_non_vie.provisionnement.a7_provisionnement.n2_puissance import (
    GRAINE_PUISSANCE, N_SIM_PUISSANCE, PAS_ARRONDI, ajuster_mack, arrondir,
    formuler, regenerer_mack, sans_objet, taux_de_detection)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, RAA,
)

_G = np.asarray(GENINS, dtype=float)
_R = np.asarray(RAA, dtype=float)


# =============================================================================
#  TPUIS-1 — LE TÉMOIN : LE GÉNÉRATEUR RESPECTE-T-IL LA NULLE ?
# =============================================================================

class TPUIS1_Temoin(unittest.TestCase):
    """⚠️ À LIRE EN PREMIER. Si ces trois-là tombent, tout le reste est faux."""

    def test_le_generateur_de_mack_respecte_les_trois_nulles(self):
        """Sans violation, le taux de détection doit avoisiner le seuil nominal.

        La borne est posée à 25 % et non à 5 % : avec 40 tirages, l'erreur type
        vaut déjà ±3,4 points au voisinage du seuil, et le test lui-même n'est
        pas parfaitement calibré (CLM-H1 mesure 6,0 % de fausse alarme). Ce
        verrou ne certifie pas une calibration fine — il attrape la faute qui
        compte : un générateur qui violerait la nulle et afficherait 53 %.
        """
        for nom, C in (('GenIns', _G), ('RAA', _R)):
            for code, test in (('CLM-H1', clm_h1_effet_calendaire),
                               ('CLM-H2', clm_h2_existence_facteurs),
                               ('CLM-H3', clm_h3_structure_variance)):
                t = taux_de_detection(C, test, n_sim=N_SIM_PUISSANCE)
                self.assertIsNotNone(t, f"{nom}/{code}")
                self.assertLess(
                    t, 25.0,
                    f"{nom}/{code} : témoin de {t:.0f} % — le générateur ne "
                    f"respecte pas la nulle de cette hypothèse, et toute "
                    f"puissance qu'il produirait serait fausse")
        print("    OK PUIS-1a témoin sous 25 % sur les 3 hypothèses × 2 "
              "triangles réels — le générateur de Mack respecte les nulles")

    def test_le_triangle_regenere_sans_violation_est_bien_de_mack(self):
        """Vérification directe, sans passer par les tests : les facteurs
        réestimés sur un triangle régénéré doivent retomber sur ceux qui ont
        servi à le produire."""
        f, s2 = ajuster_mack(_G)
        rng = np.random.default_rng(GRAINE_PUISSANCE)
        ecarts = []
        for _ in range(20):
            T = regenerer_mack(_G, f, s2, rng)
            f2, _ = ajuster_mack(T)
            ecarts.append(np.abs(f2[:4] / f[:4] - 1.0))
        moyen = float(np.mean(ecarts))
        self.assertLess(moyen, 0.05,
                        "les facteurs réestimés s'écartent de ceux qui ont "
                        "engendré le triangle : le générateur dérive")
        print(f"    OK PUIS-1b facteurs réestimés à {100 * moyen:.1f} % en "
              f"moyenne de ceux qui ont servi à régénérer")

    def test_chaque_violation_mord_vraiment(self):
        """Un paramètre de violation qui ne changerait rien rendrait la
        puissance publiée sans objet — et personne ne le verrait."""
        f, s2 = ajuster_mack(_G)
        base = regenerer_mack(_G, f, s2, np.random.default_rng(1))
        for lbl, kw in (('choc calendaire',
                         {'choc_diagonale': 5, 'ampleur': 2.0}),
                        ('ordonnée à l\'origine', {'intercept': 5.0e5}),
                        ('variance en C^2', {'expo_var': 2.0})):
            autre = regenerer_mack(_G, f, s2, np.random.default_rng(1), **kw)
            self.assertFalse(np.allclose(base, autre),
                             f"la violation « {lbl} » ne change pas le triangle")
        print("    OK PUIS-1c les trois violations modifient effectivement le "
              "triangle régénéré")


# =============================================================================
#  TPUIS-2 — CE QUI EST PUBLIÉ
# =============================================================================

class TPUIS2_Publication(unittest.TestCase):

    def test_la_puissance_est_reproductible(self):
        """Un chiffre publié dans un livrable réglementaire ne peut pas
        dépendre d'un tirage. Graine fixe, deux appels, même résultat."""
        a = puissance_clm(_G)
        b = puissance_clm(_G)
        for code in ('CLM-H1', 'CLM-H2', 'CLM-H3'):
            self.assertEqual(a[code]['puissance'], b[code]['puissance'])
            self.assertEqual(a[code]['graine'], GRAINE_PUISSANCE)
            self.assertEqual(a[code]['n_simulations'], N_SIM_PUISSANCE)
        print(f"    OK PUIS-2a deux appels rendent la même puissance "
              f"(graine {GRAINE_PUISSANCE}, {N_SIM_PUISSANCE} simulations)")

    def test_l_arrondi_est_a_la_dizaine(self):
        """40 tirages ne portent pas la décimale : publier « 71,4 % »
        suggérerait une précision qui n'existe pas."""
        for brut, attendu in ((0.0, 0), (4.9, 0), (5.1, 10), (47.0, 50),
                              (70.0, 70), (100.0, 100)):
            self.assertEqual(arrondir(brut), attendu)
        for code in ('CLM-H1', 'CLM-H2', 'CLM-H3'):
            self.assertEqual(puissance_clm(_G)[code]['puissance'] % PAS_ARRONDI,
                             0)
        print(f"    OK PUIS-2b arrondi au multiple de {PAS_ARRONDI} %")

    def test_les_hypotheses_sans_puissance_le_disent(self):
        """⚠️ NE JAMAIS INVENTER UN CHIFFRE. CLM-H4 compare des courbes
        d'extrapolation : ce n'est pas un test statistique, la notion de
        puissance n'y a pas de sens. On le dit, on ne met pas 0 %."""
        h4 = puissance_clm(_G)['CLM-H4']
        self.assertFalse(h4['mesurable'])
        self.assertNotIn('puissance', h4)
        self.assertIn("n'y a pas de sens", h4['phrase'])
        sansobj = sans_objet('un contrôle de plage')
        self.assertFalse(sansobj['mesurable'])
        print("    OK PUIS-2c CLM-H4 déclarée sans objet, aucun chiffre inventé")

    def test_le_registre_est_affirmatif(self):
        """Publier une puissance est une FORCE : cela énonce ce que le test
        pouvait voir, là où le marché publie un « validée » muet. Aucune
        formulation ne doit laisser entendre que l'outil doute de lui-même."""
        interdits = ('malheureusement', 'faible', 'insuffisant', 'hélas',
                     'limite de l', 'ne peut pas être', 'aveu', '⚠')
        for pct in (0.0, 15.0, 45.0, 75.0, 95.0):
            phrase = formuler(pct, "un effet de test", "un levier limité")
            for mot in interdits:
                self.assertNotIn(mot, phrase if mot == '⚠' else phrase.lower())
            self.assertIn('%', phrase)
        # Le bas de gamme doit tout de même être EXPLICITE sur ce qu'il signifie
        self.assertIn('absence de contradiction', formuler(10.0, 'x', 'y'))
        self.assertIn('opposable', formuler(90.0, 'x'))
        print("    OK PUIS-2d registre affirmatif sur toute la plage, et le "
              "bas de gamme dit « absence de contradiction », pas « validée »")

    def test_la_puissance_repond_a_l_ampleur(self):
        """Sur un triangle où le test a du levier, une violation plus forte
        doit être plus souvent détectée — sans quoi le chiffre ne mesure rien."""
        faible = taux_de_detection(_G, clm_h3_structure_variance, expo_var=1.2)
        forte = taux_de_detection(_G, clm_h3_structure_variance, expo_var=2.0)
        self.assertGreater(forte, faible)
        print(f"    OK PUIS-2e CLM-H3 : variance en C^1,2 → {faible:.0f} %, "
              f"en C^2 → {forte:.0f} % — la puissance suit bien l'ampleur")


# =============================================================================
#  TPUIS-3 — L'ARRIVÉE DANS LES LIVRABLES
# =============================================================================

class TPUIS3_Livrables(unittest.TestCase):
    """⚠️ CES QUATRE HYPOTHÈSES N'ATTEIGNAIENT AUCUN LIVRABLE. BFCC, Bootstrap
    et Munich avaient chacun leur fonction d'affichage ; CLM n'en avait pas.
    Les hypothèses des MÉTHODES PRINCIPALES étaient calculées, gatantes pour
    deux d'entre elles, et invisibles au lecteur du rapport."""

    def test_les_quatre_lignes_clm_existent(self):
        n2 = {'clm': verifier_hypotheses_clm(_G)}
        lignes = lignes_hypotheses_clm(n2)
        self.assertEqual([x['code'] for x in lignes],
                         ['CLM-H1', 'CLM-H2', 'CLM-H3', 'CLM-H4'])
        for x in lignes:
            self.assertTrue(x['libelle'])
            self.assertIn(x['statut'], (VALIDEE, 'À JUSTIFIER', 'NON VALIDÉE',
                                        NON_TESTABLE))
        print("    OK PUIS-3a les quatre lignes CLM sont disponibles pour les "
              "livrables, avec libellé et statut")

    def test_la_puissance_accompagne_le_verdict(self):
        n2 = {'clm': verifier_hypotheses_clm(_G)}
        par_code = {x['code']: x for x in lignes_hypotheses_clm(n2)}
        for code in ('CLM-H1', 'CLM-H2', 'CLM-H3'):
            self.assertIsNotNone(par_code[code]['puissance'])
            self.assertIn('détecterait', par_code[code]['puissance_phrase'])
        self.assertIn("n'y a pas de sens",
                      par_code['CLM-H4']['puissance_phrase'])
        print("    OK PUIS-3b chaque ligne porte sa puissance à côté de son "
              "verdict ; CLM-H4 porte sa mention de non-pertinence")

    def test_une_ligne_sans_puissance_n_en_affiche_pas(self):
        """⚠️ LE FAUX ZÉRO, ÉVITÉ DE JUSTESSE. Le rendu HTML testait
        `_s(phrase)` au lieu de la valeur brute — or `_s('')` rend « — », qui
        est vrai en Python. Les quinze hypothèses sans puissance auraient
        affiché un bloc contenant un tiret."""
        lignes = lignes_hypotheses_clm({'clm': {}})
        for x in lignes:
            self.assertEqual(x['puissance_phrase'], '')
            self.assertIsNone(x['puissance'])
        print("    OK PUIS-3c sans puissance calculée, la ligne ne porte "
              "aucune phrase — pas de tiret, pas de zéro")

    def test_on_peut_se_passer_du_calcul(self):
        """Le calcul coûte quelques secondes : les appelants qui n'en ont pas
        besoin doivent pouvoir s'en dispenser sans que rien d'autre change."""
        avec = verifier_hypotheses_clm(_G)
        sans = verifier_hypotheses_clm(_G, puissance=False)
        self.assertEqual(sans['puissance'], {})
        self.assertEqual(avec['hypotheses'].keys(), sans['hypotheses'].keys())
        for code in avec['hypotheses']:
            self.assertEqual(avec['hypotheses'][code]['statut'],
                             sans['hypotheses'][code]['statut'],
                             "le calcul de puissance a changé un verdict")
        print("    OK PUIS-3d `puissance=False` n'altère aucun verdict")


if __name__ == '__main__':
    unittest.main(verbosity=2)
