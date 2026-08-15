# -*- coding: utf-8 -*-
"""Tests N1 — le §56 confronté au roll-forward ICA 5.6.1, sur 3 arrêtés.

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️ C'EST LE PREMIER TEST DE MESURE ULTÉRIEURE DU DÉPÔT. L'oracle 5.2 ne
portait qu'un arrêté : un calcul faux qui n'aurait perdu son terme qu'à
partir du second serait passé. Ici il y en a trois.
"""
import unittest

from normes.ifrs17.mesure.declaration import (
    FORME_DATE_25,
    ContexteEvaluation,
    GroupeEvalue,
)
from normes.ifrs17.mesure.financement import (
    ASSIETTE,
    MOTIF_LRC_NON_ETEINT,
    MOTIF_TAUX_ABERRANT,
    MOTIF_TAUX_SANS_ARRETE,
    MOTIF_TAUX_SANS_SIGNATURE,
    MOTIF_TAUX_SANS_SOURCE,
    roll_forward,
    verrouiller,
)
from normes.ifrs17.mesure.lrc_paa import (
    MOTIF_FINANCEMENT_NON_CONSTRUIT,
    VERDICT_53_ELIGIBLE,
    RefusMesure,
    lrc_suivant,
)
from normes.ifrs17.oracles.angle_mort_assiette import (
    ECART_MAXIMAL_EN_PART_DU_LRC,
    ECART_MAXIMAL_PAR_CONTRAT,
    LES_DEUX_PASSENT_LES_ORACLES,
    LRC_PAR_ASSIETTE,
    PROVENANCE,
)
from normes.ifrs17.oracles.angle_mort_assiette import (
    ENTREE as ANGLE_MORT,
)
from normes.ifrs17.oracles.ica_222092 import (
    CHAINE_EXACTE_5_6_1,
    ENTREE_5_6_1,
    ROLL_FORWARD_5_6_1,
    TOLERANCE,
)

CONTEXTE = ContexteEvaluation(
    arrete='2026-12-31',
    portefeuilles=('AUTO_TR', 'MRH', 'GAV', 'RC_AUTO', 'RC_PRO', 'DO'))

#: ⚠️ LE GROUPE DE L'ORACLE, D'UN SEUL TENANT. Sa cohorte (§22, l'émission)
#: et sa date de comptabilisation initiale (§25) coïncident ici — l'exemple
#: ICA place les deux au 1er janvier 2026. ⚠️ ELLES NE COÏNCIDENT PAS
#: TOUJOURS, et c'est tout l'objet de `GroupeEvalue` : les avoir supposées
#: liées faisait refuser 2 groupes sur 18 du banc local.
GROUPE = GroupeEvalue(cohorte='2026', date_25='2026-01-01')


def roll_forward_ctx(**kw):
    """⚠️ `contexte` et `groupe` obligatoires au site de consommation."""
    return roll_forward(contexte=CONTEXTE, groupe=GROUPE,
                        forme_du_taux_verrouille=FORME_DATE_25, **kw)


def _taux():
    return verrouiller(
        ENTREE_5_6_1['taux_verrouille'],
        arrete_verrouillage='2026-01-01',
        source="oracle ICA/CIA doc 222092 section 5.6.1 — taux de l'exemple",
        actuaire_resp='Selasse Sekle')


def _mesure():
    return roll_forward_ctx(prime=ENTREE_5_6_1['prime'],
                        nb_periodes=ENTREE_5_6_1['duree_couverture_ans'],
                        taux=_taux(), verdict_53_declare=VERDICT_53_ELIGIBLE)


class T1_LOracle5_6_1(unittest.TestCase):
    """T1 — trois arrêtés, face aux valeurs publiées."""

    def test_les_trois_LRC_de_cloture_tombent_sur_l_oracle(self):
        """⚠️ LA TOLERANCE EST 0,5, ET ELLE EST MESUREE. La source conseille
        1 unite ; sur un solde de 1 040 cela vaut 0,1 %, assez lache pour
        laisser passer un defaut."""
        mesure = _mesure()
        publie = ROLL_FORWARD_5_6_1[1:]
        self.assertEqual(len(mesure), len(publie))
        for m, p in zip(mesure, publie):
            self.assertLessEqual(
                abs(m.lrc_cloture - p['lrc_cloture']), TOLERANCE,
                f"{p['arrete']} : mesure {m.lrc_cloture}, "
                f"oracle {p['lrc_cloture']}")
        obtenus = [round(m.lrc_cloture, 2) for m in mesure]
        print(f"    OK N1 : LRC de cloture {obtenus} vs oracle "
              f"{[p['lrc_cloture'] for p in publie]}")

    def test_la_convention_de_signe_est_RETOURNEE_EXPLICITEMENT(self):
        """⚠️⚠️ LE PIEGE QUE L'ORACLE PORTE DANS SON PROPRE DOCUMENT.

        La section 5.2 publie le revenu POSITIF, la 5.6.1 le publie NEGATIF.
        Ce module rend le revenu positif, comme `lrc_paa`. Le retournement se
        fait ICI, et il est ECRIT : le laisser implicite ferait passer un
        signe inverse pour une egalite.
        """
        for m, p in zip(_mesure(), ROLL_FORWARD_5_6_1[1:]):
            attendu_positif = -p['revenu_total']       # <-- LE RETOURNEMENT
            self.assertLess(p['revenu_total'], 0)      # la source est negative
            self.assertGreater(m.revenu_total, 0)      # ce module est positif
            self.assertLessEqual(abs(m.revenu_total - attendu_positif), 1.0,
                                 p['arrete'])
        print("    OK N1b : revenu retourne explicitement — source negative, "
              "mesure positive, ecart borne")

    def test_la_composante_de_financement_du_revenu_tombe_aussi(self):
        """⚠️ LA COLONNE QUE J'ALLAIS OUBLIER DE CONFRONTER.

        L'oracle publie le revenu de financement separement du revenu de
        prime (-20, -40, -61). Ne verifier que le LRC de cloture laisserait
        passer une VENTILATION fausse dont les totaux tombent juste : deux
        erreurs qui se compensent entre les deux composantes donneraient le
        bon solde. C'est vulture qui a signale le champ non lu.
        """
        for m, p in zip(_mesure(), ROLL_FORWARD_5_6_1[1:]):
            attendu = -p['revenu_financement']         # retournement declare
            self.assertLessEqual(
                abs(m.revenu_financement - attendu), TOLERANCE,
                f"{p['arrete']} : mesure {m.revenu_financement}, "
                f"oracle {attendu}")
            self.assertAlmostEqual(
                m.revenu_prime,
                ENTREE_5_6_1['prime'] / ENTREE_5_6_1['duree_couverture_ans'],
                6)
        obtenus = [round(m.revenu_financement, 2) for m in _mesure()]
        print(f"    OK N1e : revenu de financement {obtenus} vs oracle "
              f"[20, 40, 61] — la VENTILATION, pas seulement le solde")

    def test_la_charge_financiere_suit_la_chaine_non_arrondie(self):
        """⚠️ ON SE COMPARE ICI A LA CHAINE NON ARRONDIE, PAS AUX VALEURS
        PUBLIEES, et c'est dit : la source publie 41 pour 40,80. Ce test
        verifie que la mesure ne reproduit pas l'ARRONDI de presentation
        mais la valeur reelle -- sinon on ajusterait le modele sur
        l'affichage du guide."""
        for m, exact in zip(_mesure(), CHAINE_EXACTE_5_6_1):
            self.assertAlmostEqual(m.charge_financiere,
                                   exact['charge_financiere'], 2)
            self.assertAlmostEqual(m.lrc_cloture, exact['lrc_cloture'], 2)
        print("    OK N1c : charges financieres 60,00 / 40,80 / 20,81 — la "
              "valeur reelle, pas l'arrondi publie 60 / 41 / 21")

    def test_le_LRC_s_eteint_au_dernier_arrete(self):
        """⚠️ CE ZERO NE PROUVE PRESQUE RIEN, ET L'ORACLE LE DIT. Le LRC DOIT
        s'eteindre en fin de couverture : c'est structurel. Le test existe
        pour attraper un terme PERDU, pas pour valider la mesure."""
        self.assertAlmostEqual(_mesure()[-1].lrc_cloture, 0.0, 6)
        print("    OK N1d : LRC eteint au dernier arrete — controle de "
              "terme perdu, pas preuve d'exactitude")


class T1b_LAssietteEstTRANCHEE(unittest.TestCase):
    """T1b — l'arbitrage qui tenait par accident, désormais posé et testé."""

    def _mesure(self):
        t = verrouiller(ANGLE_MORT['taux'], '2026-01-01',
                        'courbe interne', 'Selasse Sekle')
        return roll_forward_ctx(prime=ANGLE_MORT['prime'],
                            nb_periodes=ANGLE_MORT['duree_couverture'],
                            frais_acquisition=ANGLE_MORT['frais_acquisition'],
                            taux=t, verdict_53_declare=VERDICT_53_ELIGIBLE)

    def test_la_mesure_suit_l_assiette_NETTE_et_PAS_la_brute(self):
        """⚠️⚠️ LE TEST QUI FAIT ECHOUER LA VARIANTE BRUTE.

        §56 ajuste << la valeur comptable du passif au titre de la couverture
        restante >> ; §55 a) ii) definit cette valeur comptable comme les
        primes reçues MOINS les frais d'acquisition. Meme expression dans les
        deux paragraphes : l'assiette est NETTE.

        Avant ce lot, ce module retenait DEJA l'assiette nette -- mais par
        accident, parce qu'elle tombe de `lrc_initial`. Rien ne l'ecrivait,
        rien ne la testait. Un arbitrage qui se trouve juste sans avoir ete
        pris tient par chance.
        """
        par_periode = {a.periode: a.lrc_cloture for a in self._mesure()}
        for periode, (brute, nette) in LRC_PAR_ASSIETTE.items():
            obtenu = par_periode[periode]
            self.assertAlmostEqual(obtenu, nette, 2,
                                   f"periode {periode} : assiette nette")
            if abs(brute - nette) > 0.01:
                self.assertNotAlmostEqual(
                    obtenu, brute, 2,
                    f"periode {periode} : la mesure suit l'assiette BRUTE, "
                    f"que le texte ecarte")
        print("    OK N1f : les 5 periodes suivent l'assiette NETTE, et "
              "AUCUNE ne coincide avec la brute la ou elles different")

    def test_l_arbitrage_est_ECRIT_avec_ses_deux_citations(self):
        """⚠️ UN ARBITRAGE NON ECRIT NE SE RELIT PAS DANS SIX MOIS."""
        for morceau in ('§56', '§55 a) ii)', 'valeur comptable',
                        'NETTE', 'même expression'):
            self.assertIn(morceau, ASSIETTE, morceau)
        print("    OK N1g : l'assiette est ecrite, avec les deux paragraphes "
              "qui la fondent")

    def test_l_angle_mort_est_reel_et_sa_provenance_est_DITE(self):
        """⚠️ CE CAS N'EST PAS UN ORACLE, ET LE FICHIER LE DIT. C'est une
        construction d'un TIERS ; personne n'a publie la bonne reponse pour
        ce cas. Il ne prouve rien -- il MONTRE ce que les oracles laissent
        passer, et c'est pour cela qu'on le garde."""
        self.assertTrue(LES_DEUX_PASSENT_LES_ORACLES)
        self.assertIn("construction d'un tiers", PROVENANCE)
        self.assertIn('AUCUNE autorité normative', PROVENANCE)
        ecarts = [abs(b - n) for b, n in LRC_PAR_ASSIETTE.values()]
        self.assertAlmostEqual(max(ecarts), ECART_MAXIMAL_PAR_CONTRAT, 2)
        # ⚠️ ET LE DENOMINATEUR EST VERIFIE, PAS SUPPOSE. Le taux publie par
        # la construction tierce rapporte l'ecart au LRC BRUT, pas au net :
        # 12,36 / 1 052,79 = 1,17 %. Ne pas le verifier laisserait une
        # lecture non controlee du tableau d'un tiers -- et c'est vulture,
        # signalant la constante non lue, qui l'a fait remarquer.
        parts = [abs(b - n) / b for b, n in LRC_PAR_ASSIETTE.values() if b]
        self.assertAlmostEqual(max(parts), ECART_MAXIMAL_EN_PART_DU_LRC, 4)
        print(f"    OK N1h : angle mort reel, ecart max "
              f"{max(ecarts):.2f} EUR par contrat soit {max(parts):.2%} du "
              f"LRC brut, provenance ecrite")


class T1c_LeLRCDoitSEteindre(unittest.TestCase):
    """T1c — le contrôle né d'une erreur que j'ai commise."""

    def test_le_roll_forward_exige_l_extinction(self):
        """⚠️ CE CONTROLE EXISTE PARCE QUE L'ERREUR A ETE COMMISE. En
        composant les primitives a la main pour confronter ce module a une
        implementation tierce, j'ai omis de relacher le revenu de
        financement : 550,66 EUR de residu, et RIEN ne l'a signale. Le
        roll-forward le refuse desormais.
        """
        t = verrouiller(0.02, '2026-01-01', 'courbe interne', 'Selasse')
        a = roll_forward_ctx(prime=4800.0, nb_periodes=10, frais_acquisition=360.0,
                         taux=t, verdict_53_declare=VERDICT_53_ELIGIBLE)
        self.assertAlmostEqual(a[-1].lrc_cloture, 0.0, 6)
        self.assertEqual(MOTIF_LRC_NON_ETEINT,
                         'lrc_non_eteint_en_fin_de_couverture')
        print(f"    OK N1i : LRC eteint a {a[-1].lrc_cloture:.6f} apres 10 "
              "periodes, avec frais d'acquisition ET financement")

    def test_les_frais_d_acquisition_sont_desormais_exprimables(self):
        """⚠️ LE CAS REEL N'ETAIT PAS EXPRIMABLE. `roll_forward` supposait
        des frais nuls ; l'appelant devait composer a la main, et c'est la
        que je me suis trompe."""
        t = verrouiller(0.02, '2026-01-01', 'courbe interne', 'Selasse')
        sans = roll_forward_ctx(prime=4800.0, nb_periodes=10, taux=t,
                            verdict_53_declare=VERDICT_53_ELIGIBLE)
        avec = roll_forward_ctx(prime=4800.0, nb_periodes=10, taux=t,
                            frais_acquisition=360.0, verdict_53_declare=VERDICT_53_ELIGIBLE)
        self.assertAlmostEqual(sans[0].lrc_ouverture, 4800.0, 6)
        self.assertAlmostEqual(avec[0].lrc_ouverture, 4440.0, 6)
        self.assertNotAlmostEqual(sans[0].lrc_cloture, avec[0].lrc_cloture, 2)
        print(f"    OK N1j : ouverture {sans[0].lrc_ouverture:.0f} sans frais "
              f"contre {avec[0].lrc_ouverture:.0f} avec — §55 a) ii)")


class T2_LeTauxEstSigne(unittest.TestCase):
    """T2 — un taux qui entre au résultat engage quelqu'un."""

    def test_sans_signataire_le_taux_est_refuse(self):
        for vide in ('', '   '):
            with self.assertRaises(RefusMesure) as ctx:
                verrouiller(0.02, '2026-01-01', 'courbe EIOPA', vide)
            self.assertEqual(ctx.exception.motif, MOTIF_TAUX_SANS_SIGNATURE)
        print("    OK N2 : pas de taux verrouille sans actuaire nomme")

    def test_sans_source_le_taux_est_refuse(self):
        """« D'ou vient ce taux » est la premiere question d'un CAC."""
        with self.assertRaises(RefusMesure) as ctx:
            verrouiller(0.02, '2026-01-01', '', 'Selasse Sekle')
        self.assertEqual(ctx.exception.motif, MOTIF_TAUX_SANS_SOURCE)
        print("    OK N2b : pas de taux sans sa source")

    def test_sans_date_de_verrouillage_le_taux_est_refuse(self):
        """§B72 d) fige le taux a la comptabilisation initiale ; sans cette
        date, il ne se rattache a aucun groupe."""
        with self.assertRaises(RefusMesure) as ctx:
            verrouiller(0.02, '', 'courbe EIOPA', 'Selasse Sekle')
        self.assertEqual(ctx.exception.motif, MOTIF_TAUX_SANS_ARRETE)
        print("    OK N2c : pas de taux sans sa date de verrouillage")

    def test_une_erreur_d_unite_est_attrapee(self):
        """⚠️ 2 SAISI POUR 2 % MULTIPLIERAIT LE LRC PAR TROIS EN UN ARRETE.
        Les bornes ne viennent d'AUCUN paragraphe -- elles n'existent que
        pour ce cas-la, et le motif le dit."""
        for aberrant in (2.0, -0.5, 100.0):
            with self.assertRaises(RefusMesure) as ctx:
                verrouiller(aberrant, '2026-01-01', 'courbe', 'Actuaire')
            self.assertEqual(ctx.exception.motif, MOTIF_TAUX_ABERRANT)
            self.assertIn("d'unité", str(ctx.exception))
        print("    OK N2d : erreur d'unite attrapee, bornes declarees comme "
              "vraisemblance et non comme norme")

    def test_le_taux_verrouille_porte_ses_quatre_champs(self):
        t = _taux()
        self.assertEqual(t.taux, 0.02)
        self.assertEqual(t.actuaire_resp, 'Selasse Sekle')
        self.assertTrue(t.source)
        self.assertTrue(t.arrete_verrouillage)
        print(f"    OK N2e : taux {t.taux}, verrouille au "
              f"{t.arrete_verrouillage}, atteste par {t.actuaire_resp}")


class T3_LeRefusDu55TombeQuandLaChargeArrive(unittest.TestCase):
    """T3 — le refus du lot précédent existait pour une raison précise."""

    def test_financement_declare_sans_charge_reste_refuse(self):
        """⚠️ LE REFUS N'A PAS ETE LEVE EN BLOC. Il visait le LRC
        silencieusement NON actualise ; il tient donc tant qu'aucune charge
        n'est fournie."""
        with self.assertRaises(RefusMesure) as ctx:
            lrc_suivant(3000.0, revenue_periode=1000.0,
                        verdict_53_declare=VERDICT_53_ELIGIBLE,
                        financement_significatif=True)
        self.assertEqual(ctx.exception.motif,
                         MOTIF_FINANCEMENT_NON_CONSTRUIT)
        print("    OK N3 : financement declare sans charge -> refus maintenu")

    def test_avec_la_charge_la_mesure_passe(self):
        obtenu = lrc_suivant(3000.0, revenue_periode=1020.0,
                             charge_financiere=60.0,
                             verdict_53_declare=VERDICT_53_ELIGIBLE,
                             financement_significatif=True)
        self.assertAlmostEqual(obtenu, 2040.0, 6)
        print(f"    OK N3b : 3000 + 60 - 1020 = {obtenu:.0f}, le refus tombe "
              "quand la charge arrive")


if __name__ == '__main__':
    unittest.main()
