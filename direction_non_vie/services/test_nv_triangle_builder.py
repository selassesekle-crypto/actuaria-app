# =============================================================================
#  Tests — nv_triangle_builder.py :: _construire_engage_depuis_individuels
#
#  Deux failles corrigées :
#   1. Le paramètre 'statut' (documenté mais jamais utilisé) est désormais un
#      filtre réel : les dossiers explicitement fermés sont exclus (un dossier
#      clos ne porte plus de charge à terminaison ; une provision résiduelle y
#      serait une donnée périmée qui gonflerait l'engagé).
#   2. L'alignement provisions → paiements se faisait sur un annee_min recalculé
#      depuis le fichier des PROVISIONS, alors que l'axe des lignes de C_paiements
#      vient du fichier des PAIEMENTS. Deux périmètres d'années différents →
#      engagé silencieusement faux. On aligne maintenant sur annee_min_paiements
#      et on ALERTE sur les provisions hors du triangle des paiements.
# =============================================================================

import unittest

import numpy as np
import pandas as pd

from direction_non_vie.services.nv_triangle_builder import NVTriangleBuilder

# Triangle des paiements cumulés — années de survenance 2020, 2021, 2022.
#   ligne 0 = 2020 (dernière colonne connue j=2, valeur 170)
#   ligne 1 = 2021 (j=1, valeur 180)
#   ligne 2 = 2022 (j=0, valeur 130)
C_PAIEMENTS = np.array([[100., 150., 170.],
                        [120., 180.,   0.],
                        [130.,   0.,   0.]])
ANNEE_MIN_PAIE = 2020


def _rapport():
    return {'alertes': [], 'infos': []}


class T1_Statut_Filtre(unittest.TestCase):
    """Faille 1 — le filtre statut exclut réellement les dossiers fermés."""

    def setUp(self):
        self.b = NVTriangleBuilder(verbose=False)

    def test_dossier_ferme_avec_provision_perimee_exclu(self):
        """Un dossier CLOS portant une provision résiduelle (999) doit être exclu :
        seul le dossier ouvert (20) compte dans la charge engagée de 2020."""
        df = pd.DataFrame({
            'annee_survenance':    [2020, 2020],
            'evaluation_courante': [20.0, 999.0],
            'statut':              ['ouvert', 'ferme'],
        })
        rap = _rapport()
        C = self.b._construire_engage_depuis_individuels(
            df, C_PAIEMENTS, rap, annee_min_paiements=ANNEE_MIN_PAIE)
        # 2020 : diagonale = 170 + 20 (le 999 du dossier fermé est écarté)
        self.assertAlmostEqual(C[0, 2], 190.0, places=2)
        self.assertNotAlmostEqual(C[0, 2], 170.0 + 999.0, places=2)
        self.assertTrue(any('statut fermé' in a for a in rap['alertes']))
        print("    OK T1a statut : dossier fermé (999) exclu, engagé 2020 = 190 (pas 1169)")

    def test_contradiction_ferme_avec_provision_non_nulle_signalee(self):
        """CONTRADICTION dans la source — statut fermé MAIS provision non nulle. Le
        statut dit « plus rien à payer », le montant dit le contraire. Le dossier reste
        exclu (cohérent avec le statut) mais l'incohérence est SIGNALÉE avec le compte
        exact et le montant écarté. Sans ça, 5 000 € disparaissaient silencieusement,
        avec le même message qu'un dossier clos parfaitement normal."""
        df = pd.DataFrame({
            'annee_survenance':    [2020,     2020,   2020,  2021],
            'evaluation_courante': [20.0,   5000.0,    0.0, 300.0],
            'statut':              ['ouvert', 'clos', 'clos', 'clos'],
        })
        rap = _rapport()
        C = self.b._construire_engage_depuis_individuels(
            df, C_PAIEMENTS, rap, annee_min_paiements=ANNEE_MIN_PAIE)
        # exclusion effective : seul le dossier ouvert (20) compte pour 2020
        self.assertAlmostEqual(C[0, 2], 190.0, places=2)
        self.assertAlmostEqual(C[1, 1], 180.0, places=2)   # 2021 : le clos 300 exclu
        # alerte de CONTRADICTION : 2 dossiers (5000 et 300), pas 3 (le clos à 0 est normal)
        contradiction = [a for a in rap['alertes'] if 'VÉRIFICATION REQUISE' in a]
        self.assertEqual(len(contradiction), 1, rap['alertes'])
        self.assertIn('2 dossier(s)', contradiction[0])          # compte exact
        self.assertIn('5,300', contradiction[0])                 # montant écarté total
        print(f"    OK T1d contradiction : 2 dossiers fermés à provision non nulle "
              f"(5 300 écartés) signalés")

    def test_ferme_a_provision_nulle_ne_declenche_pas_la_contradiction(self):
        """Contre-épreuve : un dossier clos SANS provision est parfaitement normal —
        il ne doit PAS déclencher l'alerte de contradiction (sinon fausse alarme)."""
        df = pd.DataFrame({
            'annee_survenance':    [2020,     2020],
            'evaluation_courante': [20.0,      0.0],
            'statut':              ['ouvert', 'clos'],
        })
        rap = _rapport()
        self.b._construire_engage_depuis_individuels(
            df, C_PAIEMENTS, rap, annee_min_paiements=ANNEE_MIN_PAIE)
        self.assertFalse(any('VÉRIFICATION REQUISE' in a for a in rap['alertes']))
        self.assertTrue(any('statut fermé' in a for a in rap['alertes']))   # exclusion tracée
        print("    OK T1e clos à provision nulle : aucune fausse alarme de contradiction")

    def test_aucune_colonne_statut_tout_inclus_et_signale(self):
        """CAS CRITIQUE — fichier SANS aucune colonne de statut. Le comportement
        DANGEREUX serait de tout exclure (provision totale = 0, silencieusement). Le
        SÛR : tout inclus (comportement historique) + alerte explicite. On vérifie
        les DEUX : provisions bien intégrées (90) ET alerte d'absence de statut."""
        df = pd.DataFrame({
            'annee_survenance':    [2020, 2021, 2022],
            'evaluation_courante': [20.0, 30.0, 40.0],
        })
        rap = _rapport()
        C = self.b._construire_engage_depuis_individuels(
            df, C_PAIEMENTS, rap, annee_min_paiements=ANNEE_MIN_PAIE)
        # tout inclus : les trois provisions sont intégrées (pas de zéro silencieux)
        self.assertAlmostEqual(C[0, 2], 190.0, places=2)   # 170 + 20
        self.assertAlmostEqual(C[1, 1], 210.0, places=2)   # 180 + 30
        self.assertAlmostEqual(C[2, 0], 170.0, places=2)   # 130 + 40
        total_provisions = (C[0, 2] - 170.0) + (C[1, 1] - 180.0) + (C[2, 0] - 130.0)
        self.assertAlmostEqual(total_provisions, 90.0, places=2)  # 90, JAMAIS 0
        # et l'absence de statut est SIGNALÉE (pas silencieuse)
        self.assertTrue(any('Aucune colonne de statut' in a for a in rap['alertes']))
        print("    OK T1c sans colonne statut : tout inclus (provisions=90, pas 0) + alerte")

    def test_statut_non_reconnu_conserve_et_signale(self):
        """CAS 4 — la colonne existe mais la valeur est illisible : faute de frappe,
        code métier non prévu, valeur vide, NaN. Le dossier est CONSERVÉ (exclure sur
        un statut incompris ferait disparaître une provision réelle) et l'anomalie est
        SIGNALÉE — sans quoi une typo sur « fermé » le rendrait invisible au filtre."""
        for libelle, valeur in (('code métier', 'XYZ_CODE_METIER'),
                                ('faute de frappe', 'fremé'),
                                ('valeur vide', ''),
                                ('valeur NaN', None)):
            df = pd.DataFrame({
                'annee_survenance':    [2020, 2020],
                'evaluation_courante': [20.0, 100.0],
                'statut':              ['ouvert', valeur],
            })
            rap = _rapport()
            C = self.b._construire_engage_depuis_individuels(
                df, C_PAIEMENTS, rap, annee_min_paiements=ANNEE_MIN_PAIE)
            # conservé : 170 + 20 + 100 = 290 (jamais 190, qui signifierait exclusion)
            self.assertAlmostEqual(C[0, 2], 290.0, places=2, msg=libelle)
            self.assertTrue(any('NON RECONNU' in a for a in rap['alertes']), libelle)
        print("    OK T1b statut non reconnu (typo/code/vide/NaN) : conservé (290) + alerte")

    def test_statut_ouvert_reconnu_sans_fausse_alerte(self):
        """Contre-épreuve du cas 4 : un statut ouvert RECONNU ne doit pas être pris
        pour « non reconnu » (sinon l'alerte crierait au loup à chaque fichier sain)."""
        for valeur in ('ouvert', 'OPEN', '  En_Cours  ', 'actif'):
            df = pd.DataFrame({
                'annee_survenance':    [2020],
                'evaluation_courante': [20.0],
                'statut':              [valeur],
            })
            rap = _rapport()
            C = self.b._construire_engage_depuis_individuels(
                df, C_PAIEMENTS, rap, annee_min_paiements=ANNEE_MIN_PAIE)
            self.assertAlmostEqual(C[0, 2], 190.0, places=2, msg=valeur)
            self.assertFalse(any('NON RECONNU' in a for a in rap['alertes']), valeur)
        print("    OK T1f statuts ouverts reconnus (casse/espaces) : aucune fausse alerte")


class T2_Alignement_Annees(unittest.TestCase):
    """Faille 2 — l'alignement sur l'axe des paiements + l'alerte de désalignement."""

    def setUp(self):
        self.b = NVTriangleBuilder(verbose=False)

    def test_sain_aligne_fonctionne_comme_avant(self):
        """(a) Années alignées (provisions 2020-2022 = paiements 2020-2022) :
        top-up correct sur chaque diagonale, AUCUNE alerte de désalignement."""
        df = pd.DataFrame({
            'annee_survenance':    [2020, 2021, 2022],
            'evaluation_courante': [20.0, 30.0, 40.0],
        })
        rap = _rapport()
        C = self.b._construire_engage_depuis_individuels(
            df, C_PAIEMENTS, rap, annee_min_paiements=ANNEE_MIN_PAIE)
        self.assertAlmostEqual(C[0, 2], 190.0, places=2)   # 2020 : 170 + 20
        self.assertAlmostEqual(C[1, 1], 210.0, places=2)   # 2021 : 180 + 30
        self.assertAlmostEqual(C[2, 0], 170.0, places=2)   # 2022 : 130 + 40
        self.assertFalse(any('absente(s) du triangle' in a for a in rap['alertes']))
        print("    OK T2a sain aligné : diagonales 190/210/170, aucune alerte")

    def test_desaligne_declenche_alerte(self):
        """(b) Provisions 2021-2023 vs paiements 2020-2022 : l'année 2023 est HORS
        du triangle des paiements → ALERTE claire + provision ignorée, et 2021 est
        placée sur la BONNE ligne (1), pas décalée sur la ligne 0 comme avant."""
        df = pd.DataFrame({
            'annee_survenance':    [2021, 2022, 2023],
            'evaluation_courante': [30.0, 40.0, 50.0],
        })
        rap = _rapport()
        C = self.b._construire_engage_depuis_individuels(
            df, C_PAIEMENTS, rap, annee_min_paiements=ANNEE_MIN_PAIE)
        # alerte de désalignement mentionnant 2023
        self.assertTrue(any('2023' in a and 'absente(s) du triangle' in a
                            for a in rap['alertes']))
        # 2021 → ligne 1 (correct), 2022 → ligne 2 ; 2020 (ligne 0) SANS provision
        self.assertAlmostEqual(C[0, 2], 170.0, places=2)   # 2020 inchangé (pas de 2021 décalé ici)
        self.assertAlmostEqual(C[1, 1], 210.0, places=2)   # 2021 sur sa vraie ligne
        self.assertAlmostEqual(C[2, 0], 170.0, places=2)   # 2022
        print("    OK T2b désaligné : 2023 hors triangle → alerte + ignorée ; 2021 bien placée ligne 1")

    def test_none_axe_non_verifiable_alerte(self):
        """Sans annee_min_paiements : l'ancien comportement positionnel subsiste mais
        n'est plus SILENCIEUX — une alerte dit que l'alignement n'a pas pu être vérifié."""
        df = pd.DataFrame({
            'annee_survenance':    [2020, 2021, 2022],
            'evaluation_courante': [20.0, 30.0, 40.0],
        })
        rap = _rapport()
        self.b._construire_engage_depuis_individuels(df, C_PAIEMENTS, rap)
        self.assertTrue(any('NE PEUT PAS être' in a for a in rap['alertes']))
        print("    OK T2c sans axe : alignement non vérifiable → alerte (plus silencieux)")


if __name__ == '__main__':
    unittest.main()
