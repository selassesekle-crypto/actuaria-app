# -*- coding: utf-8 -*-
"""Tests Q1 — la répartition se reçoit et se publie, elle ne se déduit pas.

⚠️ GATE : `py -m unittest discover -s normes -t .`
"""
import unittest

from normes.ifrs17.mesure.attribution import (
    CRITERE,
    MOTIF_ATTRIBUTION_SANS_SIGNATURE,
    MOTIF_ATTRIBUTION_VIDE,
    MOTIF_CATEGORIE_DANS_LES_DEUX,
    MOTIF_COUT_EVAPORE,
    declarer,
    resume,
)
from normes.ifrs17.mesure.lrc_paa import (
    VERDICT_53_ELIGIBLE,
    RefusMesure,
    periode_annuelle,
)
from normes.ifrs17.oracles.ica_222092 import ATTENDU_5_2, ENTREE_5_2

#: L'exemple ICA 5.2, tel qu'une entité le déclarerait.
ATTRIBUABLES = {'frais_acquisition': 200.0, 'frais_maintenance': 50.0}
NON_ATTRIBUABLES = {'frais_acquisition_non_attribuables': 30.0,
                    'frais_maintenance_non_attribuables': 25.0}


def _declaration(**kw):
    base = {'attribuables': ATTRIBUABLES,
            'non_attribuables': NON_ATTRIBUABLES,
            'actuaire_resp': 'Selasse Sekle', 'arrete': '2026-12-31'}
    base.update(kw)
    return declarer(**base)


class T1_LaDeclarationEstRecue(unittest.TestCase):
    """T1 — reçue et publiée, jamais déduite."""

    def test_les_deux_totaux_sortent(self):
        d = _declaration()
        self.assertAlmostEqual(d.total_attribuable, 250.0, 6)
        self.assertAlmostEqual(d.total_non_attribuable, 55.0, 6)
        print(f"    OK Q1 : {d.total_attribuable:.0f} attribuables, "
              f"{d.total_non_attribuable:.0f} non attribuables")

    def test_le_total_non_attribuable_alimente_la_periode(self):
        """⚠️ LE RACCORD AVEC §55 : c'est CE total qui sort du resultat
        d'assurance, et l'exemple ICA 5.2 le chiffre a 55."""
        e = ENTREE_5_2
        p = periode_annuelle(
            primes_attendues=e['prime'],
            duree_couverture=e['duree_couverture_ans'],
            frais_acquisition_attribuables=e['frais_acquisition_attribuables'],
            frais_maintenance_attribuables=(
                e['frais_maintenance_attribuables_an1']),
            frais_non_attribuables=_declaration().total_non_attribuable,
            verdict_53_declare=VERDICT_53_ELIGIBLE)
        self.assertAlmostEqual(p.autres_charges,
                               ATTENDU_5_2['autres_charges'], 6)
        self.assertAlmostEqual(p.resultat, ATTENDU_5_2['resultat'], 6)
        self.assertEqual(p.motif_resultat, '')
        print(f"    OK Q1b : la declaration alimente la periode — "
              f"resultat {p.resultat:.0f}, comme l'oracle")

    def test_le_resume_publie_le_CRITERE_avec_les_montants(self):
        """⚠️ UNE REPARTITION SANS LA REGLE QUI L'A GUIDEE N'EST PAS
        VERIFIABLE PAR UN TIERS : il lirait des chiffres sans savoir contre
        quoi les juger."""
        txt = resume(_declaration())
        self.assertIn('B66 d)', txt)
        self.assertIn('TELS QUE', txt)
        self.assertIn('Selasse Sekle', txt)
        self.assertIn('2026-12-31', txt)
        self.assertIn('55.00', txt)
        print("    OK Q1c : le resume publie le critere, le signataire, "
              "l'arrete et les montants")

    def test_le_critere_dit_que_la_liste_est_illustrative(self):
        """⚠️ LE POINT QUI A DECIDE DE LA FORME DE CE MODULE. « tels que »
        et « certains » : la liste de B66 d) n'est pas limitative, et une
        meme categorie peut se partager. Aucune regle calculable ne peut en
        sortir -- le module recoit, il ne deduit pas."""
        self.assertIn('illustrative', CRITERE)
        self.assertIn('jamais limitative', CRITERE)
        self.assertIn("acte de l'entité", CRITERE)
        print("    OK Q1d : le critere publie dit lui-meme pourquoi il n'est "
              "pas calculable")


class T2_LeSeulControleCalculable(unittest.TestCase):
    """T2 — qu'aucun coût ne s'évapore entre les deux paniers."""

    def test_une_somme_incomplete_est_refusee(self):
        """⚠️ DES CHARGES QUI S'EVAPORENT GONFLENT LE RESULTAT SANS QUE RIEN
        NE LE DISE. C'est le seul controle que ce module puisse faire, et il
        est reel."""
        with self.assertRaises(RefusMesure) as ctx:
            _declaration(total_remis=400.0)      # 305 declares, 95 perdus
        self.assertEqual(ctx.exception.motif, MOTIF_COUT_EVAPORE)
        self.assertIn('95', str(ctx.exception))
        print("    OK Q2 : 305 declares contre 400 remis -> refus, les 95 "
              "manquants sont nommes")

    def test_une_somme_complete_passe(self):
        d = _declaration(total_remis=305.0)
        self.assertAlmostEqual(
            d.total_attribuable + d.total_non_attribuable, 305.0, 6)
        print("    OK Q2b : 305 declares contre 305 remis -> accepte")

    def test_sans_total_remis_le_controle_n_a_PAS_lieu(self):
        """⚠️ ET SON ABSENCE NE SE DEGUISE PAS EN SUCCES. Omettre le total
        n'est pas le declarer juste : le controle ne se fait simplement
        pas, et c'est a l'appelant de le savoir."""
        d = _declaration()
        self.assertAlmostEqual(d.total_attribuable
                               + d.total_non_attribuable, 305.0, 6)
        print("    OK Q2c : sans total remis, aucun controle d'evaporation "
              "-- la declaration passe telle quelle")


class T3_LesRefus(unittest.TestCase):
    """T3 — ce que la déclaration ne peut pas être."""

    def test_sans_signataire_la_declaration_est_refusee(self):
        for vide in ('', '  '):
            with self.assertRaises(RefusMesure) as ctx:
                _declaration(actuaire_resp=vide)
            self.assertEqual(ctx.exception.motif,
                             MOTIF_ATTRIBUTION_SANS_SIGNATURE)
        print("    OK Q3 : pas de repartition sans actuaire nomme")

    def test_sans_arrete_la_declaration_est_refusee(self):
        with self.assertRaises(RefusMesure) as ctx:
            _declaration(arrete='')
        self.assertEqual(ctx.exception.motif,
                         MOTIF_ATTRIBUTION_SANS_SIGNATURE)
        print("    OK Q3b : une repartition vaut pour SON arrete")

    def test_une_categorie_des_deux_cotes_est_refusee(self):
        """⚠️ B66 d) ADMET QU'UNE CATEGORIE SE PARTAGE — « certains » frais
        de developpement. Mais elle doit alors etre declaree en DEUX postes
        NOMMES, pas en un seul compte deux fois."""
        with self.assertRaises(RefusMesure) as ctx:
            declarer(attribuables={'formation': 10.0},
                     non_attribuables={'formation': 5.0},
                     actuaire_resp='Selasse Sekle', arrete='2026-12-31')
        self.assertEqual(ctx.exception.motif, MOTIF_CATEGORIE_DANS_LES_DEUX)
        self.assertIn('formation', str(ctx.exception))
        print("    OK Q3c : une categorie des deux cotes -> refus, avec le "
              "chemin admis (deux postes nommes)")

    def test_une_declaration_vide_n_est_pas_une_declaration(self):
        """⚠️ VIDE N'EST PAS « TOUT EST ATTRIBUABLE ». C'est une absence, et
        elle doit se dire -- meme lecon que `PAA_NON_ETABLI`."""
        with self.assertRaises(RefusMesure) as ctx:
            declarer(attribuables={}, non_attribuables={},
                     actuaire_resp='Selasse Sekle', arrete='2026-12-31')
        self.assertEqual(ctx.exception.motif, MOTIF_ATTRIBUTION_VIDE)
        print("    OK Q3d : declaration vide refusee, jamais lue comme "
              "'tout est attribuable'")


if __name__ == '__main__':
    unittest.main()
