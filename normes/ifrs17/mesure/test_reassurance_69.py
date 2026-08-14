# -*- coding: utf-8 -*-
"""Tests AB1 — l'éligibilité PAA de la réassurance détenue (§69).

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️ AUCUN ORACLE, mais ce lot porte DEUX confrontations réelles : le calcul
du §69 b) est de l'arithmétique sur des dates, contrôlable par un tiers, et
le partage qu'il produit sur le portefeuille livré — 7 ouvertes, 6 fermées —
est un résultat vérifiable.
"""
import datetime
import unittest

from normes.ifrs17.mesure.lrc_paa import RefusMesure
from normes.ifrs17.mesure.reassurance_69 import (
    BASE_RISQUES_ATTACHANTS,
    BASE_SINISTRES_SURVENUS,
    MOTIF_BASE_NON_DECLAREE,
    MOTIF_DATES_INVALIDES,
    PAA_RA_69A_NON_EVALUEE,
    PAA_RA_ELIGIBLE,
    PAA_RA_NON_ETABLI,
    PORTE_69A,
    VERDICTS,
    Traite,
    comptes_69,
    duree_couverture_69b,
    eligibilite_69,
)

D = datetime.date
DEBUT, FIN = D(2026, 1, 1), D(2026, 12, 31)

#: Les polices souscrites pendant l'annee de traite debordent d'un an.
SOUS_JACENTES = (D(2027, 12, 30),)
#: Cas decennale : la couverture sous-jacente court dix ans de plus.
SOUS_JACENTES_DO = (D(2036, 12, 30),)


def _traite(base, ident='QP-TEST-2026'):
    return Traite(ident, base, DEBUT, FIN)


class AB1_AucunVerdictNeDitINELIGIBLE(unittest.TestCase):
    """AB1 — la leçon du §53, appliquée mot pour mot."""

    def test_aucun_des_trois_verdicts_ne_conclut_a_l_ineligibilite(self):
        """⚠️ LE SOCLE A PAYE CETTE LECON. Un verdict nomme `NON_ELIGIBLE`
        affirmait une conclusion que le code ne peut pas atteindre, faute de
        pouvoir apprecier la porte qualitative -- et c'est le NOM que
        consomment les agregats, pas la phrase du motif.
        """
        for v in VERDICTS:
            self.assertNotIn('NON_ELIGIBLE', v, v)
            self.assertNotIn('INELIGIBLE', v, v)
        self.assertIn('69A', PAA_RA_69A_NON_EVALUEE)
        print("    OK AB1 : aucun des 3 verdicts §69 ne conclut a "
              "l'ineligibilite")

    def test_69b_ferme_rend_69A_NON_EVALUEE_et_non_un_refus(self):
        """⚠️ ECHOUER A (b) N'ETABLIT RIEN SUR (a). §70 est le miroir du
        §54 : sa clause operatoire est une ATTENTE de l'entite, et ses
        facteurs sont introduits par << par exemple >>, sans seuil."""
        v, motif = eligibilite_69(_traite(BASE_RISQUES_ATTACHANTS),
                                  fins_sous_jacentes=SOUS_JACENTES)
        self.assertEqual(v, PAA_RA_69A_NON_EVALUEE)
        self.assertIn('§69 b) est fermé', motif)
        self.assertIn('reste ouverte en droit', motif)
        self.assertIn('§70', PORTE_69A)
        print("    OK AB1b : §69 b) ferme -> 69A_NON_EVALUEE, la porte (a) "
              "reste ouverte")

    def test_les_trois_cles_sont_comptees_meme_a_zero(self):
        """⚠️ << 0 non etabli >> doit etre indiscernable de << je n'ai pas
        regarde >> -- meme lecon que le registre du socle."""
        c = comptes_69([PAA_RA_ELIGIBLE])
        self.assertEqual(set(c), set(VERDICTS))
        self.assertEqual(c[PAA_RA_NON_ETABLI], 0)
        print(f"    OK AB1c : les {len(VERDICTS)} cles existent meme a zero")


class AB2_LaBaseCOMMANDELaFrontiere(unittest.TestCase):
    """AB2 — les deux branches diffèrent réellement, et c'est mesuré."""

    def test_les_deux_bases_donnent_des_verdicts_DIFFERENTS(self):
        """⚠️⚠️ LA VERIFICATION EXIGEE APRES LE MECANISME FICTIF D'HIER.
        Avant d'offrir un parametre de choix, verifier que les branches
        donnent des resultats DIFFERENTS -- et l'ecrire comme test. Ici,
        MEMES dates de traite, MEMES polices sous-jacentes, deux bases :
        deux verdicts opposes.
        """
        attach = eligibilite_69(_traite(BASE_RISQUES_ATTACHANTS),
                                fins_sous_jacentes=SOUS_JACENTES)
        survenus = eligibilite_69(_traite(BASE_SINISTRES_SURVENUS),
                                  fins_sous_jacentes=SOUS_JACENTES)
        self.assertEqual(attach[0], PAA_RA_69A_NON_EVALUEE)
        self.assertEqual(survenus[0], PAA_RA_ELIGIBLE)
        self.assertNotEqual(attach[0], survenus[0])
        print(f"    OK AB2 : memes dates, deux bases -> {attach[0]} contre "
              f"{survenus[0]}. Les branches different REELLEMENT")

    def test_en_sinistres_survenus_les_sous_jacentes_sont_IGNOREES(self):
        """⚠️ L'ERREUR QUI A ETE COMMISE PUIS CORRIGEE. Appliquer
        l'extension a TOUS les traites rendait 13 fermes sur 13. Un traite
        en sinistres survenus couvre les sinistres SURVENUS dans sa periode,
        quelle que soit la date des polices."""
        sans = duree_couverture_69b(_traite(BASE_SINISTRES_SURVENUS))
        avec = duree_couverture_69b(_traite(BASE_SINISTRES_SURVENUS),
                                    SOUS_JACENTES_DO)
        self.assertAlmostEqual(sans, avec, 9)
        self.assertLessEqual(avec, 1.0)
        print(f"    OK AB2b : sinistres survenus, {avec:.3f} an avec ou sans "
              "les sous-jacentes -- elles ne comptent pas")

    def test_en_risques_attachants_elles_ETENDENT_la_periode(self):
        court = duree_couverture_69b(_traite(BASE_RISQUES_ATTACHANTS),
                                     SOUS_JACENTES)
        long = duree_couverture_69b(_traite(BASE_RISQUES_ATTACHANTS),
                                    SOUS_JACENTES_DO)
        self.assertGreater(court, 1.0)
        self.assertGreater(long, 10.0)
        print(f"    OK AB2c : risques attachants, {court:.3f} an et "
              f"{long:.3f} an selon les polices — la parenthese du §69 b) "
              "opere")


class AB3_LeCasNON_ETABLI(unittest.TestCase):
    """AB3 — ne pas pouvoir calculer n'est pas être éligible."""

    def test_risques_attachants_sans_sous_jacentes_est_NON_ETABLI(self):
        """⚠️ PRENDRE LA SEULE DUREE DU TRAITE DONNERAIT << ELIGIBLE >> A
        TORT sur un traite annuel dont les polices debordent -- c'est
        exactement le cas des six quote-parts du portefeuille livre."""
        v, motif = eligibilite_69(_traite(BASE_RISQUES_ATTACHANTS))
        self.assertEqual(v, PAA_RA_NON_ETABLI)
        self.assertIn('à tort', motif)
        self.assertIn('DÉCLARÉ, non établi', motif)
        print("    OK AB3 : risques attachants sans sous-jacentes -> "
              "NON_ETABLI, jamais ELIGIBLE par defaut")

    def test_une_attente_69a_DECLAREE_ouvre_la_porte(self):
        """⚠️ ET ELLE ENGAGE L'ENTITE, PAS LE CODE. §70 en confie
        l'appreciation a elle seule."""
        v, motif = eligibilite_69(
            _traite(BASE_RISQUES_ATTACHANTS), fins_sous_jacentes=SOUS_JACENTES,
            attente_69a_declaree='ecart attendu non significatif, note du '
                                 '15/01/2026 signee par l actuaire')
        self.assertEqual(v, PAA_RA_ELIGIBLE)
        self.assertIn('DÉCLARÉE et signée', motif)
        self.assertIn('engage l\'entité', motif)
        print("    OK AB3b : attente §69 a) declaree -> ELIGIBLE, et le "
              "motif dit qui elle engage")

    def test_une_attente_FICTIVE_ne_l_ouvre_pas(self):
        """⚠️ LA PORTE DE SIGNATURE VAUT ICI AUSSI : `A_RENSEIGNER` n'est
        pas une attente."""
        for fictif in ('A_RENSEIGNER', 'TBD', 'N/A', '', '   '):
            v, _ = eligibilite_69(_traite(BASE_RISQUES_ATTACHANTS),
                                  fins_sous_jacentes=SOUS_JACENTES,
                                  attente_69a_declaree=fictif)
            self.assertEqual(v, PAA_RA_69A_NON_EVALUEE, fictif)
        print("    OK AB3c : 5 attentes fictives -> aucune n'ouvre la porte "
              "§69 a)")


class AB4_LePortefeuilleLIVRE(unittest.TestCase):
    """AB4 — le partage 7/6, reproductible par un tiers."""

    #: Les 13 traites du portefeuille livre, dates reelles (0,997 an).
    TRAITES = tuple(
        (f'{p}-{b}', BASE_RISQUES_ATTACHANTS if b == 'QP'
         else BASE_SINISTRES_SURVENUS)
        for p in ('RC_AUTO', 'MRH', 'AUTO_TR', 'RC_PRO', 'GAV', 'DO')
        for b in ('QP', 'XL')) + (('MRH-CAT', BASE_SINISTRES_SURVENUS),)

    def test_le_partage_est_de_SEPT_ouvertes_et_SIX_fermees(self):
        """⚠️ LE LIVRABLE DE CE LOT. Six quote-parts en risques attachants
        voient leur porte §69 b) se fermer parce que les polices
        sous-jacentes debordent ; les sept traites en sinistres survenus
        restent dans l'annee."""
        verdicts = []
        for ident, base in self.TRAITES:
            sous = SOUS_JACENTES_DO if ident.startswith('DO') else SOUS_JACENTES
            v, _ = eligibilite_69(Traite(ident, base, DEBUT, FIN),
                                  fins_sous_jacentes=sous)
            verdicts.append(v)
        c = comptes_69(verdicts)
        self.assertEqual(c[PAA_RA_ELIGIBLE], 7)
        self.assertEqual(c[PAA_RA_69A_NON_EVALUEE], 6)
        self.assertEqual(c[PAA_RA_NON_ETABLI], 0)
        print(f"    OK AB4 : {c[PAA_RA_ELIGIBLE]} ouvertes, "
              f"{c[PAA_RA_69A_NON_EVALUEE]} fermees sur "
              f"{len(self.TRAITES)} traites")

    def test_la_decennale_est_le_cas_extreme(self):
        """⚠️ COHERENT AVEC LE SOCLE : le sous-jacent decennal fermait deja
        la porte §53 b). Sa quote-part ferme la porte §69 b) pour la meme
        raison."""
        d = duree_couverture_69b(
            Traite('QP-DO-2026', BASE_RISQUES_ATTACHANTS, DEBUT, FIN),
            SOUS_JACENTES_DO)
        self.assertGreater(d, 10.0)
        print(f"    OK AB4b : la quote-part decennale couvre {d:.2f} ans au "
              "sens du §69 b)")


class AB5_LesRefus(unittest.TestCase):
    """AB5 — ce que le module refuse plutôt que de le deviner."""

    def test_une_base_non_declaree_est_refusee(self):
        """⚠️ LA DEVINER FERAIT BASCULER UN VERDICT -- c'est toute la
        difference entre 7/6 et 13/0."""
        for mauvaise in (None, '', 'quote-part', 'risques_attachants'):
            with self.assertRaises(RefusMesure) as ctx:
                duree_couverture_69b(_traite(mauvaise))
            self.assertEqual(ctx.exception.motif, MOTIF_BASE_NON_DECLAREE)
        print("    OK AB5 : 4 bases non declarees -> refus, y compris la "
              "forme minuscule du fichier source")

    def test_des_dates_invalides_sont_refusees(self):
        t = Traite('X', BASE_SINISTRES_SURVENUS, FIN, DEBUT)
        with self.assertRaises(RefusMesure) as ctx:
            duree_couverture_69b(t)
        self.assertEqual(ctx.exception.motif, MOTIF_DATES_INVALIDES)
        print("    OK AB5b : fin avant debut -> refus")


if __name__ == '__main__':
    unittest.main()
