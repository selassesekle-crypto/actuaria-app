# -*- coding: utf-8 -*-
"""Tests R1 — B120 boucle sur la vie du groupe, ou il dit pourquoi non.

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️ LE SEUL CONTRÔLE DE C4 QUI NE DÉPEND D'AUCUNE SOURCE. L'identité de B120
tient sur n'importe quel portefeuille ; l'oracle ICA 5.6.1 ne fait que
confirmer la lecture, il n'en est pas le fondement.
"""
import unittest

from normes.ifrs17.mesure.bouclage_b120 import (
    MOTIF_AUCUNE_PERIODE,
    verifier,
)
from normes.ifrs17.mesure.declaration import ContexteEvaluation
from normes.ifrs17.mesure.financement import roll_forward, verrouiller
from normes.ifrs17.mesure.lrc_paa import (
    VERDICT_53_ELIGIBLE,
    RefusMesure,
)
from normes.ifrs17.oracles.ica_222092 import ENTREE_5_6_1, ROLL_FORWARD_5_6_1

COHORTE = '2026'
CONTEXTE = ContexteEvaluation(arrete='2026-12-31',
                              portefeuilles=('AUTO_TR', 'MRH', 'GAV', 'RC_AUTO', 'RC_PRO', 'DO'))


def roll_forward_ctx(**kw):
    """⚠️ `contexte` obligatoire au site de consommation."""
    return roll_forward(contexte=CONTEXTE,
                        cohorte_du_groupe=COHORTE, **kw)



def _mesure():
    t = verrouiller(ENTREE_5_6_1['taux_verrouille'], '2026-01-01',
                    "oracle ICA/CIA doc 222092 section 5.6.1",
                    'Selasse Sekle')
    return roll_forward_ctx(prime=ENTREE_5_6_1['prime'],
                        nb_periodes=ENTREE_5_6_1['duree_couverture_ans'],
                        taux=t, verdict_53_declare=VERDICT_53_ELIGIBLE)


class T1_LIdentiteSurLaMesureDuDepot(unittest.TestCase):
    """T1 — trois arrêtés, une identité de bout en bout."""

    def test_le_bouclage_est_exact_sur_la_mesure(self):
        """⚠️ EXACT, PAS << DANS UNE TOLERANCE >>. L'identite de B120 est
        arithmetique ; seule l'erreur de virgule flottante est toleree."""
        a = _mesure()
        b = verifier(revenus_periode=[x.revenu_total for x in a],
                     primes_encaissees=ENTREE_5_6_1['prime'],
                     charges_financieres=sum(x.charge_financiere for x in a))
        self.assertTrue(b.boucle, b.motif)
        self.assertEqual(b.motif, '')
        self.assertLess(abs(b.ecart), 1e-9)
        print(f"    OK R1 : {b.nb_periodes} periodes, {b.total_revenu:.4f} "
              f"de produits contre {b.attendu:.4f} attendus, ecart "
              f"{b.ecart:+.9f}")

    def test_le_bouclage_tient_aussi_sur_l_oracle_publie(self):
        """⚠️ A L'UNITE PRES, ET C'EST L'ARRONDI DE PRESENTATION.

        La source publie ses valeurs arrondies : 3 121 de produits contre
        3 000 + 122 = 3 122 attendus. L'ecart d'une unite est le meme
        arrondi que celui deja mesure sur le roll-forward, pas un defaut de
        l'identite. On le compare donc AVEC la tolerance de l'oracle, la ou
        la mesure du depot, elle, boucle exactement.
        """
        p = ROLL_FORWARD_5_6_1[1:]
        b = verifier(revenus_periode=[-x['revenu_total'] for x in p],
                     primes_encaissees=ENTREE_5_6_1['prime'],
                     charges_financieres=sum(x['charge_financiere']
                                             for x in p),
                     epsilon=1.0)
        self.assertTrue(b.boucle, b.motif)
        self.assertLessEqual(abs(b.ecart), 1.0)
        print(f"    OK R1b : sur l'oracle publie, ecart {b.ecart:+.1f} — "
              f"l'arrondi de presentation, pas l'identite")


class T2_CeQueLeBouclageAttrape(unittest.TestCase):
    """T2 — ce qu'un contrôle de période ne peut pas voir."""

    def test_une_periode_manquante_est_attrapee(self):
        """⚠️ CHAQUE PERIODE RESTANTE EST JUSTE, ET POURTANT C'EST FAUX.

        Perdre un arrete ne rend aucune des deux autres incorrecte : un
        controle qui compare periode par periode aux valeurs publiees ne
        verrait rien. B120 le voit, parce qu'il regarde le TOTAL.
        """
        a = _mesure()
        b = verifier(revenus_periode=[x.revenu_total for x in a[:-1]],
                     primes_encaissees=ENTREE_5_6_1['prime'],
                     charges_financieres=sum(x.charge_financiere for x in a))
        self.assertFalse(b.boucle)
        self.assertEqual(b.nb_periodes, 2)
        self.assertIn('B120 ne boucle pas', b.motif)
        print(f"    OK R2 : une periode perdue -> ecart {b.ecart:+.1f}, "
              f"attrape alors que les 2 restantes sont justes")

    def test_un_produit_compte_deux_fois_est_attrape(self):
        a = _mesure()
        r = [x.revenu_total for x in a]
        b = verifier(revenus_periode=r + [r[0]],
                     primes_encaissees=ENTREE_5_6_1['prime'],
                     charges_financieres=sum(x.charge_financiere for x in a))
        self.assertFalse(b.boucle)
        self.assertGreater(b.ecart, 0)
        print(f"    OK R2b : un produit compte deux fois -> ecart "
              f"{b.ecart:+.1f}")

    def test_le_motif_n_accuse_pas_le_calcul(self):
        """⚠️ UN BOUCLAGE QUI ECHOUE N'EST PAS FORCEMENT UNE ERREUR DE
        CALCUL : une composante d'investissement non declaree produit le
        meme symptome. Le motif porte les DEUX lectures."""
        a = _mesure()
        b = verifier(revenus_periode=[x.revenu_total for x in a[:-1]],
                     primes_encaissees=ENTREE_5_6_1['prime'],
                     charges_financieres=sum(x.charge_financiere for x in a))
        self.assertIn('DEUX LECTURES POSSIBLES', b.motif)
        self.assertIn("composante", b.motif)
        self.assertIn('affectation', b.motif)
        print("    OK R2c : le motif propose deux lectures, il n'en impose "
              "aucune")

    def test_une_composante_d_investissement_declaree_retablit_le_bouclage(self):
        """B120 b) : les composantes d'investissement sortent du produit."""
        a = _mesure()
        r = [x.revenu_total for x in a]
        ci = 500.0
        b = verifier(revenus_periode=[x - ci / len(r) for x in r],
                     primes_encaissees=ENTREE_5_6_1['prime'],
                     charges_financieres=sum(x.charge_financiere for x in a),
                     composantes_investissement=ci)
        self.assertTrue(b.boucle, b.motif)
        print(f"    OK R2d : {ci:.0f} de composante d'investissement "
              f"declaree -> le bouclage tient")


class T3_LesRefus(unittest.TestCase):
    """T3 — zéro période n'est pas un bouclage réussi."""

    def test_aucune_periode_est_refuse(self):
        """⚠️⚠️ LE PIEGE QUE CE DEPOT TRAQUE DEPUIS LE DEBUT. Rendre
        `boucle=True` sur une liste vide serait la meme faute qu'une gate
        rendant << Ran 0 tests >> et sortant en 0."""
        with self.assertRaises(RefusMesure) as ctx:
            verifier(revenus_periode=[], primes_encaissees=3000.0)
        self.assertEqual(ctx.exception.motif, MOTIF_AUCUNE_PERIODE)
        self.assertIn('Ran 0 tests', str(ctx.exception))
        print("    OK R3 : zero periode -> refus, jamais un bouclage vide "
              "presente comme reussi")

    def test_un_produit_negatif_signale_un_retournement_non_fait(self):
        with self.assertRaises(RefusMesure) as ctx:
            verifier(revenus_periode=[-1020.0], primes_encaissees=3000.0)
        self.assertEqual(ctx.exception.motif, 'montant_negatif')
        print("    OK R3b : produit negatif -> refus, convention de signe "
              "signalee")


if __name__ == '__main__':
    unittest.main()
