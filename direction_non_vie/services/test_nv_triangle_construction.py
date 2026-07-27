# =============================================================================
#  Tests — nv_triangle_construction.py (Bloc II, module 4)
#
#  Couvre les 3 cas d'entrée × 2 bases, les défauts déjà corrigés ailleurs et
#  re-vérifiés ici (négatifs jamais transformés, zone future masquée, filtre
#  statut à 4 cas, alignement par année réelle), la DETTE IMPÉRATIVE
#  (diagonale_paiements disponible même en base charges) et le comportement
#  ajusté sur les primes (construire ce qui est possible, signaler le reste).
# =============================================================================

import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import direction_non_vie.services.nv_triangle_construction as C4
from direction_non_vie.services.nv_triangle_construction import (
    METHODES_REQUERANT_PRIMES, ConstructionImpossible, TrianglesConstruits,
    construire_triangles, construire_depuis_long, detecter_cumulativite,
    deriver_charges_depuis_provisions, primes_requises,
)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, _TRI_RECOURS_FORT, _TRI_TOUT_DECROISSANT,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────
CUM = np.array([[100., 150., 170.],
                [120., 180.,   0.],
                [130.,   0.,   0.]])
INC = np.array([[1000., 500., 200., 80.],
                [1100., 550., 220.,  0.],
                [1050., 520.,   0.,  0.],
                [1200.,   0.,   0.,  0.]])

LONG_PAIE = pd.DataFrame({
    'annee_survenance': [2020, 2020, 2020, 2021, 2021, 2022],
    'annee_developpement': [0, 1, 2, 0, 1, 0],
    'montant_paye': [100., 50., 20., 120., 60., 130.],
})
LONG_DEUX_MESURES = LONG_PAIE.assign(
    montant_charge=[180., -5., 0., 200., 10., 210.])
PROVISIONS = pd.DataFrame({
    'annee_survenance': [2020, 2021, 2022],
    'evaluation_courante': [20., 30., 40.],
})


class T1_Cumulativite(unittest.TestCase):
    """Détection à 3 états — on ne devine plus sur l'ambigu."""

    def test_cumule_et_incremental_nets(self):
        self.assertEqual(detecter_cumulativite(GENINS), 'cumule')
        self.assertEqual(detecter_cumulativite(CUM), 'cumule')
        self.assertEqual(detecter_cumulativite(INC), 'incremental')
        print("    OK T1a cumulé net / incrémental net correctement reconnus")

    def test_recours_est_ambigu_et_refuse_de_deviner(self):
        """LE cas qui était FAUX avant : l'ancienne détection classait un cumulé
        à recours en « incrémental » et le pipeline le cumsommait en silence
        (1000, 2000, 2500, 2400 → 1000, 3000, 5500, 7900)."""
        for nom, T in (('RECOURS_FORT', _TRI_RECOURS_FORT),
                       ('TOUT_DECROISSANT', _TRI_TOUT_DECROISSANT)):
            self.assertEqual(detecter_cumulativite(T), 'ambigu', nom)
            with self.assertRaises(ConstructionImpossible, msg=nom) as ctx:
                construire_triangles(paiements=T)              # mode 'auto'
            self.assertIn('AMBIG', str(ctx.exception).upper())
            self.assertIn('recours', str(ctx.exception))
        print("    OK T1b recours → 'ambigu' : refuse de deviner, message explicite")

    def test_mode_declare_leve_l_ambiguite(self):
        r = construire_triangles(paiements=_TRI_RECOURS_FORT, mode_paiements='cumule')
        np.testing.assert_allclose(r.paiements[0][:4], [1000., 2000., 2500., 2400.])
        print("    OK T1c mode déclaré 'cumule' : triangle conservé tel quel")

    def test_incremental_est_cumule_et_zone_future_masquee(self):
        r = construire_triangles(paiements=INC, mode_paiements='incremental')
        np.testing.assert_allclose(r.paiements[0], [1000., 1500., 1700., 1780.])
        # cellules futures (i + j >= n) remises à zéro après cumsum
        self.assertEqual(r.paiements[3, 1], 0.0)
        self.assertEqual(r.paiements[2, 2], 0.0)
        print("    OK T1d incrémental cumulé + zone future masquée")


class T2_Trois_Cas_Deux_Bases(unittest.TestCase):
    """Les 3 cas d'entrée × 2 bases."""

    def test_matrice_cumulee_paiements_et_charges(self):
        r = construire_triangles(paiements=CUM, charges=CUM * 1.2,
                                 mode_paiements='cumule', mode_charges='cumule')
        self.assertIsNotNone(r.paiements)
        self.assertIsNotNone(r.charges)
        self.assertEqual(r.n_annees, 3)
        print("    OK T2a cas cumulé × (paiements + charges)")

    def test_matrice_incrementale_les_deux_bases(self):
        r = construire_triangles(paiements=INC, charges=INC,
                                 mode_paiements='incremental',
                                 mode_charges='incremental')
        np.testing.assert_allclose(r.paiements, r.charges)
        print("    OK T2b cas incrémental × 2 bases")

    def test_long_paiements(self):
        r = construire_triangles(paiements=LONG_PAIE)
        np.testing.assert_allclose(r.paiements[0][:3], [100., 150., 170.])
        self.assertEqual(r.annee_min, 2020)
        print("    OK T2c cas long → paiements (100, 150, 170)")

    def test_long_avec_montant_charge_direct(self):
        """Charges DIRECTES : le tableau porte montant_charge → même pivot."""
        r = construire_triangles(paiements=LONG_DEUX_MESURES,
                                 charges=LONG_DEUX_MESURES)
        np.testing.assert_allclose(r.paiements[0][:3], [100., 150., 170.])
        np.testing.assert_allclose(r.charges[0][:3], [180., 175., 175.])
        print("    OK T2d cas long → charges directes depuis montant_charge")

    def test_long_charges_derivees_des_provisions(self):
        """Charges DÉRIVÉES : provisions posées sur la diagonale des paiements.
        Capacité qui n'existait que côté application, ramenée dans la mainline."""
        r = construire_triangles(paiements=LONG_PAIE, charges=PROVISIONS)
        # 2020 : diagonale j=2 → 170 + 20 ; 2021 : j=1 → 180 + 30 ; 2022 : 130 + 40
        self.assertAlmostEqual(r.charges[0, 2], 190.0, places=2)
        self.assertAlmostEqual(r.charges[1, 1], 210.0, places=2)
        self.assertAlmostEqual(r.charges[2, 0], 170.0, places=2)
        print("    OK T2e cas long → charges dérivées (190 / 210 / 170)")

    def test_cas_mixte_matrice_et_long_exige_annee_min(self):
        """Cas mixte paiements-en-MATRICE + charges dérivées de provisions : une
        matrice est POSITIONNELLE, elle ne porte aucun axe d'années. Poser les
        provisions au hasard produirait des charges fausses en silence — le module
        refuse et réclame annee_min."""
        with self.assertRaises(ConstructionImpossible) as ctx:
            construire_triangles(paiements=CUM, charges=PROVISIONS,
                                 mode_paiements='cumule')
        self.assertIn('annee_min', str(ctx.exception))
        # avec l'année fournie, l'alignement redevient possible
        r = construire_triangles(paiements=CUM, charges=PROVISIONS,
                                 mode_paiements='cumule', annee_min=2020)
        self.assertAlmostEqual(r.charges[0, 2], 190.0, places=2)
        self.assertAlmostEqual(r.charges[1, 1], 210.0, places=2)
        print("    OK T2f cas mixte : refuse sans annee_min, correct avec (190/210)")


class T3_Defauts_Deja_Corriges(unittest.TestCase):
    """Défauts corrigés ailleurs, re-vérifiés ici : ce module ne les réintroduit pas."""

    def test_negatifs_jamais_transformes(self):
        """Le validator faisait `.abs()` sur les montants négatifs (recours
        détruit en silence). Ici ils traversent ET sont signalés."""
        rapport = {'alertes': [], 'infos': []}
        C, _ = construire_depuis_long(LONG_DEUX_MESURES, 'montant_charge', rapport)
        self.assertAlmostEqual(C[0, 1], 175.0, places=2)      # 180 + (−5), pas 185
        self.assertTrue(any('négatif' in a for a in rapport['alertes']))
        print("    OK T3a montants négatifs conservés (175 = 180−5) + signalés")

    def test_statut_les_quatre_cas(self):
        base, _ = construire_depuis_long(LONG_PAIE, 'montant_paye')
        cas = {
            'aucune colonne': (PROVISIONS, 'Aucune colonne de statut'),
            'fermé simple':   (PROVISIONS.assign(statut=['ouvert', 'clos', 'ouvert']),
                               'statut fermé exclu'),
            'contradiction':  (PROVISIONS.assign(statut=['clos', 'ouvert', 'ouvert']),
                               'VÉRIFICATION REQUISE'),
            'non reconnu':    (PROVISIONS.assign(statut=['fremé', 'ouvert', 'ouvert']),
                               'NON RECONNU'),
        }
        for libelle, (df, attendu) in cas.items():
            rap = {'alertes': [], 'infos': []}
            deriver_charges_depuis_provisions(base, df, 2020, rap)
            self.assertTrue(any(attendu in a for a in rap['alertes']),
                            f"{libelle} : alerte '{attendu}' absente")
        # le dossier fermé est bien EXCLU du calcul
        rap = {'alertes': [], 'infos': []}
        Cc = deriver_charges_depuis_provisions(
            base, PROVISIONS.assign(statut=['clos', 'ouvert', 'ouvert']), 2020, rap)
        self.assertAlmostEqual(Cc[0, 2], 170.0, places=2)     # 2020 : provision écartée
        print("    OK T3b statut : les 4 cas signalés, dossier fermé exclu")

    def test_alignement_par_annee_reelle(self):
        """Les provisions doivent viser l'ANNÉE, pas la position : un décalage de
        périmètre produisait des charges silencieusement fausses."""
        base, _ = construire_depuis_long(LONG_PAIE, 'montant_paye')   # 2020-2022
        prov = pd.DataFrame({'annee_survenance': [2021, 2022, 2023],
                             'evaluation_courante': [30., 40., 50.]})
        rap = {'alertes': [], 'infos': []}
        Cc = deriver_charges_depuis_provisions(base, prov, 2020, rap)
        self.assertAlmostEqual(Cc[0, 2], 170.0, places=2)   # 2020 : AUCUNE provision
        self.assertAlmostEqual(Cc[1, 1], 210.0, places=2)   # 2021 sur SA ligne
        self.assertTrue(any('2023' in a for a in rap['alertes']))   # hors triangle
        print("    OK T3c alignement par année réelle + alerte hors périmètre")

    def test_dimensions_alignees_pour_munich(self):
        petit = np.array([[10., 20.], [15., 0.]])
        r = construire_triangles(paiements=CUM, charges=petit,
                                 mode_paiements='cumule', mode_charges='cumule')
        self.assertEqual(r.paiements.shape, r.charges.shape)
        self.assertTrue(any('dimensions différentes' in a
                            for a in r.rapport['alertes']))
        print("    OK T3d triangles alignés en dimensions (comparaison Munich)")


class T4_Dette_Imperative(unittest.TestCase):
    """diagonale_paiements disponible MÊME en base charges — le mécanisme concret."""

    def test_diagonale_presente_en_base_charges(self):
        r = construire_triangles(paiements=CUM, charges=CUM * 1.2,
                                 mode_paiements='cumule', mode_charges='cumule',
                                 base_reference='charges')
        self.assertEqual(r.base_reference, 'charges')
        self.assertIsNotNone(r.diagonale_paiements)
        # payé à date : 170 (2020, j=2), 180 (2021, j=1), 130 (2022, j=0)
        np.testing.assert_allclose(r.diagonale_paiements, [170., 180., 130.])
        # et la référence de projection est bien le triangle des charges
        np.testing.assert_allclose(r.reference, r.charges)
        print("    OK T4a base charges : diagonale des PAIEMENTS disponible (170/180/130)")

    def test_diagonale_presente_en_base_paiements(self):
        r = construire_triangles(paiements=CUM, mode_paiements='cumule')
        np.testing.assert_allclose(r.diagonale_paiements, [170., 180., 130.])
        np.testing.assert_allclose(r.reference, r.paiements)
        print("    OK T4b base paiements : diagonale disponible également")

    def test_base_charges_sans_paiements_alerte(self):
        """Sans paiements, le BE sur charges serait l'IBNR pur : il faut le DIRE."""
        r = construire_triangles(charges=CUM, mode_charges='cumule',
                                 base_reference='charges')
        self.assertIsNone(r.diagonale_paiements)
        self.assertTrue(any('IBNR' in a and 'PUR' in a for a in r.rapport['alertes']))
        print("    OK T4c base charges sans paiements : alerte IBNR pur explicite")

    def test_base_reference_inconstructible_leve(self):
        with self.assertRaises(ConstructionImpossible):
            construire_triangles(paiements=CUM, mode_paiements='cumule',
                                 base_reference='charges')
        with self.assertRaises(ConstructionImpossible):
            construire_triangles(paiements=CUM, base_reference='inconnue')
        print("    OK T4d base demandée non constructible / inconnue → lève")


class T5_Primes(unittest.TestCase):
    """Comportement AJUSTÉ : construire ce qui est possible, signaler le reste."""

    def test_methode_sans_besoin_sans_primes_ok(self):
        r = construire_triangles(paiements=CUM, mode_paiements='cumule',
                                 methodes_demandees=('chain_ladder', 'mack'))
        self.assertFalse(r.primes_requises)
        self.assertEqual(r.methodes_bloquees, ())
        print("    OK T5a CL + Mack sans primes : rien de bloqué")

    def test_methode_avec_besoin_et_primes_ok(self):
        r = construire_triangles(paiements=CUM, mode_paiements='cumule',
                                 primes=[1000., 1100., 1200.],
                                 methodes_demandees=('bornhuetter_ferguson',))
        self.assertTrue(r.primes_requises)
        self.assertTrue(r.primes_disponibles)
        self.assertEqual(r.methodes_bloquees, ())
        np.testing.assert_allclose(r.primes, [1000., 1100., 1200.])
        print("    OK T5b BF avec primes : disponible, rien de bloqué")

    def test_primes_absentes_ne_bloquent_pas_tout(self):
        """L'ajustement de Selasse : un actuaire qui veut CL+Mack et a coché BF
        par réflexe ne doit PAS perdre CL+Mack. Le triangle est construit, seule
        BF est signalée bloquée."""
        r = construire_triangles(
            paiements=CUM, mode_paiements='cumule',
            methodes_demandees=('chain_ladder', 'mack', 'bornhuetter_ferguson'))
        self.assertIsNotNone(r.paiements)                     # construit quand même
        self.assertEqual(r.methodes_bloquees, ('bornhuetter_ferguson',))
        self.assertTrue(any('ne pourra' in a for a in r.rapport['alertes']))
        print("    OK T5c primes absentes : triangle construit, seule BF bloquée")

    def test_liste_est_le_point_d_extension_unique(self):
        """ANTI-DÉRIVE : ajouter 'benktander' au frozenset suffit — aucune autre
        ligne du module ne nomme de méthode. Un `if methode == 'bf'` en dur
        quelque part ferait échouer ce test."""
        self.assertFalse(primes_requises(('benktander',)))     # pas encore dans la liste
        etendu = frozenset(METHODES_REQUERANT_PRIMES | {'benktander'})
        with patch.object(C4, 'METHODES_REQUERANT_PRIMES', etendu):
            self.assertTrue(primes_requises(('benktander',)))
            r = construire_triangles(paiements=CUM, mode_paiements='cumule',
                                     methodes_demandees=('benktander', 'mack'))
            self.assertEqual(r.methodes_bloquees, ('benktander',))
        # hors du patch, le comportement d'origine revient
        self.assertFalse(primes_requises(('benktander',)))
        print("    OK T5d point d'extension : 'benktander' pris en compte par la seule liste")

    def test_primes_plus_courtes_completees_et_signalees(self):
        r = construire_triangles(paiements=CUM, mode_paiements='cumule',
                                 primes=[1000.])
        self.assertEqual(len(r.primes), 3)
        self.assertTrue(any('plus court' in a for a in r.rapport['alertes']))
        print("    OK T5e vecteur de primes trop court : complété + signalé")


class T7_Repere_Annees_Impose(unittest.TestCase):
    """Option A — `annees_reference` impose le repère au lieu de le déduire.

    Sans repère, un SOUS-ENSEMBLE perd les années où il n'a aucun sinistre et sa
    zone connue rétrécit (le masquage `i+j >= n` utilise le n LOCAL) : deux
    sous-ensembles d'un même portefeuille deviennent ni comparables ni
    recombinables. Le repère imposé règle les deux à la fois.
    """

    def test_non_regression_sans_repere(self):
        """Le nouveau paramètre ne change RIEN quand il n'est pas fourni."""
        sans = construire_depuis_long(LONG_PAIE, 'montant_paye')
        avec_none = construire_depuis_long(LONG_PAIE, 'montant_paye', None, None)
        np.testing.assert_allclose(sans[0], avec_none[0])
        self.assertEqual(sans[1], avec_none[1])
        # et par le dispatcher
        r1 = construire_triangles(paiements=LONG_PAIE)
        r2 = construire_triangles(paiements=LONG_PAIE, annees_reference=None)
        np.testing.assert_allclose(r1.paiements, r2.paiements)
        print("    OK T7a non-régression : sans repère, comportement identique")

    def test_repere_impose_conserve_les_annees_absentes(self):
        """Un sous-ensemble ne couvrant qu'une année garde tout le repère."""
        sous = LONG_PAIE[LONG_PAIE['annee_survenance'] == 2021]
        sans, amin_sans = construire_depuis_long(sous, 'montant_paye')
        self.assertEqual(sans.shape[0], 1)          # une seule ligne : 2021
        self.assertEqual(amin_sans, 2021)
        avec, amin_avec = construire_depuis_long(
            sous, 'montant_paye', None, (2020, 3, 3))
        self.assertEqual(avec.shape, (3, 3))        # les 3 années du portefeuille
        self.assertEqual(amin_avec, 2020)
        self.assertAlmostEqual(avec[0].sum(), 0.0)  # 2020 : aucun sinistre → zéros
        self.assertAlmostEqual(avec[1, 0], 120.0)   # 2021 sur SA ligne
        print("    OK T7b repère imposé : 3 années conservées, 2021 bien placée")

    def test_groupe_vide_est_nominal(self):
        """Cas NOMINAL (ex. seuil LLT ne capturant personne) : triangle de zéros,
        PAS d'exception. Sans repère, la même table vide lève."""
        vide = LONG_PAIE.iloc[0:0]
        with self.assertRaises(ConstructionImpossible):
            construire_depuis_long(vide, 'montant_paye')          # sans repère
        C, amin = construire_depuis_long(vide, 'montant_paye', None, (2020, 3, 3))
        self.assertEqual(C.shape, (3, 3))
        self.assertAlmostEqual(float(C.sum()), 0.0)
        self.assertEqual(amin, 2020)
        print("    OK T7c groupe vide + repère : triangle de zéros, aucune exception")

    def test_lignes_hors_repere_ignorees_et_signalees(self):
        """Une ligne hors du repère imposé est ignorée — mais jamais en silence."""
        rapport = {'alertes': [], 'infos': []}
        C, _ = construire_depuis_long(LONG_PAIE, 'montant_paye', rapport, (2020, 2, 3))
        self.assertEqual(C.shape, (2, 3))           # 2022 hors repère
        self.assertTrue(any('hors du repère' in a for a in rapport['alertes']))
        print("    OK T7d ligne hors repère : ignorée + alertée")


class T6_Garde_Fous_Et_Forme(unittest.TestCase):
    """Erreurs propres et contrat de sortie."""

    def test_aucune_source_leve(self):
        with self.assertRaises(ConstructionImpossible):
            construire_triangles()
        print("    OK T6a aucune source → lève")

    def test_axe_de_developpement_absent_leve(self):
        df = pd.DataFrame({'annee_survenance': [2020], 'montant_paye': [100.]})
        with self.assertRaises(ConstructionImpossible):
            construire_triangles(paiements=df)
        print("    OK T6b aucun axe de développement → lève")

    def test_axe_derive_de_annee_paiement(self):
        df = pd.DataFrame({'annee_survenance': [2020, 2020, 2021],
                           'annee_paiement':   [2020, 2021, 2021],
                           'montant_paye':     [100., 50., 120.]})
        r = construire_triangles(paiements=df)
        np.testing.assert_allclose(r.paiements[0][:2], [100., 150.])
        print("    OK T6c axe dérivé de annee_paiement − annee_survenance")

    def test_synthese_json_serialisable(self):
        import json
        r = construire_triangles(paiements=CUM, charges=CUM, mode_paiements='cumule',
                                 mode_charges='cumule', primes=[1., 2., 3.])
        s = r.synthese()
        json.dumps(s)
        for cle in ('paiements_construits', 'charges_construites',
                    'diagonale_paiements_disponible', 'base_reference',
                    'methodes_bloquees'):
            self.assertIn(cle, s)
        self.assertIsInstance(r, TrianglesConstruits)
        print("    OK T6d synthese() sérialisable, clés du contrat présentes")


if __name__ == '__main__':
    unittest.main()
