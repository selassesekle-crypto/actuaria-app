# -*- coding: utf-8 -*-
"""Tests Z1 — le passif au titre des sinistres survenus (§59 b).

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️⚠️ AUCUN ORACLE, ET LE TRIANGLE DISPONIBLE PORTE « CADENCES INVENTÉES ».
Ces tests établissent des invariants et des refus. Ils ne disent RIEN de
l'exactitude d'une réserve — une projection sur des cadences inventées rend
un nombre, pas une provision.
"""
import unittest

from normes.ifrs17.mesure.declaration import ContexteEvaluation
from normes.ifrs17.mesure.lic import (
    MOTIF_ACTUALISATION_INCOHERENTE,
    MOTIF_AUCUNE_CELLULE,
    MOTIF_DISPENSE_NON_DECLAREE,
    MOTIF_PROJECTION_INFERIEURE,
    MOTIF_PROJECTION_NON_DECLAREE,
    MOTIF_TRIANGLE_INCOHERENT,
    Cellule,
    declarer_projection,
    developpement_130,
    passif_sinistres,
)
from normes.ifrs17.mesure.lrc_paa import RefusMesure

CONTEXTE = ContexteEvaluation(arrete='2026-12-31',
                              portefeuilles=('AUTO_TR', 'MRH', 'GAV', 'RC_AUTO', 'RC_PRO', 'DO'))


def passif_sinistres_ctx(cellules, projection, **kw):
    """⚠️ `contexte` obligatoire — voir `eprouver_ctx`."""
    return passif_sinistres(cellules, projection, CONTEXTE, **kw)


#: Un triangle a deux survenances, CUMULE -- comme un vrai.
TRIANGLE = (
    Cellule('RC_AUTO', 2025, 0, 1000.0, 1600.0),
    Cellule('RC_AUTO', 2025, 1, 1400.0, 1650.0),
    Cellule('RC_AUTO', 2026, 0, 900.0, 1500.0),
)


def _proj(ultime=3400.0):
    return declarer_projection(ultime=ultime, methode='Chain Ladder pondere',
                               actuaire_resp='Selasse Sekle',
                               arrete='2026-12-31')


class Z1_LObserveEtLeDeclareNeSeMelangentPas(unittest.TestCase):
    """Z1 — le triangle observe, l'ultime declare, l'IBNR leur difference."""

    def test_les_cumules_ne_s_additionnent_PAS_entre_developpements(self):
        """⚠️ LE PIEGE ARITHMETIQUE DU TRIANGLE. Les cellules sont CUMULEES :
        additionner la colonne compterait chaque paiement autant de fois
        qu'il y a de developpements. Seule la DERNIERE cellule connue de
        chaque survenance porte l'observation.
        """
        p = passif_sinistres_ctx(TRIANGLE, _proj(), dispense_59b=True)
        # RC_AUTO 2025 -> dev 1 (1650), RC_AUTO 2026 -> dev 0 (1500)
        self.assertAlmostEqual(p.charge_connue, 1650.0 + 1500.0, 6)
        self.assertAlmostEqual(p.paiements, 1400.0 + 900.0, 6)
        # la somme NAIVE de toutes les cellules serait bien plus grande
        naive = sum(c.charge_cumulee for c in TRIANGLE)
        self.assertNotAlmostEqual(p.charge_connue, naive, 2)
        print(f"    OK Z1 : charge connue {p.charge_connue:.0f} par les "
              f"dernieres cellules, et NON {naive:.0f} par somme naive")

    def test_l_IBNR_est_la_DIFFERENCE_et_herite_de_l_incertitude(self):
        """⚠️ L'IBNR N'EST PAS OBSERVE. Il vaut ultime declare moins charge
        connue : toute son incertitude vient du DECLARE."""
        p = passif_sinistres_ctx(TRIANGLE, _proj(3400.0), dispense_59b=True)
        self.assertAlmostEqual(p.ibnr, 3400.0 - p.charge_connue, 6)
        self.assertAlmostEqual(p.provision_connue,
                               p.charge_connue - p.paiements, 6)
        print(f"    OK Z1b : IBNR {p.ibnr:.0f} = ultime {3400:.0f} - charge "
              f"connue {p.charge_connue:.0f}")

    def test_un_ultime_inferieur_a_la_charge_connue_est_refuse(self):
        """⚠️ L'ULTIME EST LA CHARGE FINALE : il ne peut pas etre plus petit
        que ce qui est deja survenu ET evalue. Un IBNR negatif se declare et
        se motive, il ne se produit pas par accident."""
        with self.assertRaises(RefusMesure) as ctx:
            passif_sinistres_ctx(TRIANGLE, _proj(1000.0), dispense_59b=True)
        self.assertEqual(ctx.exception.motif, MOTIF_PROJECTION_INFERIEURE)
        self.assertIn('INFÉRIEUR', str(ctx.exception))
        print("    OK Z1c : ultime < charge connue -> refus, IBNR negatif "
              "jamais produit par accident")


class Z2_LesReservesDESCENDENT(unittest.TestCase):
    """Z2 — ce que les données ne permettent pas d'affirmer, écrit."""

    def test_les_cadences_inventees_marquent_TOUTE_sortie(self):
        """⚠️ LE TRIANGLE LIVRE PORTE << SYNTHETIQUE, CADENCES INVENTEES >>.
        Une projection dessus rend UN NOMBRE, PAS UNE RESERVE. La reserve
        accompagne tout montant qui en descend."""
        p = passif_sinistres_ctx(TRIANGLE, _proj(), dispense_59b=True)
        self.assertIn('SOURCE NON ATTESTÉE', p.motif)
        self.assertIn('PAS UNE RÉSERVE', p.motif)
        self.assertIn('opposable', p.motif)
        print("    OK Z2 : la reserve des cadences inventees marque la "
              "sortie -- un nombre, pas une reserve")

    def test_une_source_attestee_leve_cette_reserve_LA_seulement(self):
        p = passif_sinistres_ctx(TRIANGLE, _proj(), source_attestee=True,
                             dispense_59b=True)
        self.assertNotIn('SOURCE NON ATTESTÉE', p.motif)
        # ⚠️ mais la reserve sur la dispense, elle, RESTE
        self.assertIn('§59 b)', p.motif)
        print("    OK Z2b : attester la source leve SA reserve, pas celle "
              "de la dispense")

    def test_la_dispense_dit_que_la_moyenne_n_est_qu_un_PROXY(self):
        """⚠️ §59 b) PORTE SUR LE DELAI << A COMPTER DE LA DATE DU SINISTRE >>,
        contrat par contrat. Une duree moyenne de portefeuille sous un an
        peut recouvrir une queue bien plus longue."""
        p = passif_sinistres_ctx(TRIANGLE, _proj(), dispense_59b=True)
        self.assertFalse(p.actualisation_faite)
        self.assertIn('DATE DU SINISTRE', p.motif)
        self.assertIn('proxy', p.motif)
        print("    OK Z2c : la dispense publie que la moyenne n'est qu'un "
              "proxy du critere par sinistre")

    def test_ni_actualisation_ni_dispense_est_REFUSE(self):
        """⚠️ RENDRE UN PASSIF NON ACTUALISE SANS LE DIRE SERAIT RENDRE UN
        CHIFFRE FAUX EN SILENCE. La dispense existe, mais elle s'exerce."""
        with self.assertRaises(RefusMesure) as ctx:
            passif_sinistres_ctx(TRIANGLE, _proj())
        self.assertEqual(ctx.exception.motif, MOTIF_DISPENSE_NON_DECLAREE)
        self.assertIn('§36', str(ctx.exception))
        print("    OK Z2d : ni actualisation ni dispense -> REFUS")


class Z2b_LeChiffrePrincipalEstVERIFIE(unittest.TestCase):
    """Z2b — le champ que personne ne lisait, et ce qu'il cachait."""

    def test_le_LIC_publie_porte_bien_ultime_moins_paiements(self):
        """⚠️ QUATRIEME SIGNALEMENT VULTURE, QUATRIEME VRAI MANQUE. Ni
        `lic_avant_risque` ni `ultime_declare` n'etaient lus par un test --
        et `lic_avant_risque` est LE CHIFFRE PRINCIPAL de ce module. Un
        champ publie que rien ne lit est un champ que rien ne verifie.
        """
        p = passif_sinistres_ctx(TRIANGLE, _proj(3400.0), dispense_59b=True)
        self.assertAlmostEqual(p.ultime_declare, 3400.0, 6)
        self.assertAlmostEqual(p.lic_avant_risque, 3400.0 - p.paiements, 6)
        print(f"    OK Z2e : LIC {p.lic_avant_risque:.0f} = ultime "
              f"{p.ultime_declare:.0f} - paiements {p.paiements:.0f}")

    def test_une_actualisation_SUPERIEURE_au_brut_est_refusee(self):
        """⚠️⚠️ CE QUE LE CHAMP NON LU CACHAIT VRAIMENT. Sous actualisation,
        le module RECOPIAIT le parametre de l'appelant sans jamais le
        confronter a l'ultime : un montant sans aucun rapport avec ce
        triangle passait sans que rien ne le dise. L'actualisation DIMINUE,
        toujours.
        """
        brut = 3400.0 - 2300.0          # ultime - paiements
        with self.assertRaises(RefusMesure) as ctx:
            passif_sinistres_ctx(TRIANGLE, _proj(3400.0),
                             actualisation=brut + 500.0)
        self.assertEqual(ctx.exception.motif, MOTIF_ACTUALISATION_INCOHERENTE)
        self.assertIn('DIMINUE', str(ctx.exception).upper())
        print(f"    OK Z2f : actualise > brut ({brut:.0f}) -> REFUS, "
              "l'actualisation diminue toujours")

    def test_une_actualisation_plausible_passe_et_est_publiee(self):
        brut = 3400.0 - 2300.0
        p = passif_sinistres_ctx(TRIANGLE, _proj(3400.0),
                             actualisation=brut * 0.95)
        self.assertTrue(p.actualisation_faite)
        self.assertAlmostEqual(p.lic_avant_risque, brut * 0.95, 6)
        self.assertLess(p.lic_avant_risque, brut)
        print(f"    OK Z2g : actualise {p.lic_avant_risque:.2f} < brut "
              f"{brut:.0f}, accepte et publie")

    def test_une_actualisation_negative_est_refusee(self):
        with self.assertRaises(RefusMesure) as ctx:
            passif_sinistres_ctx(TRIANGLE, _proj(3400.0), actualisation=-1.0)
        self.assertEqual(ctx.exception.motif, MOTIF_ACTUALISATION_INCOHERENTE)
        print("    OK Z2h : actualisation negative -> refus")


class Z3_LArticle130(unittest.TestCase):
    """Z3 — trois années ne sont pas dix, et le tableau le dit."""

    def test_la_limite_du_130_est_NOMMEE_pas_laissee_decouvrir(self):
        """⚠️ §130 DEMANDE DE REMONTER AUSSI LOIN QUE LE DELAI LE PLUS LONG,
        PLAFONNE A DIX ANS. Publier trois colonnes sans le dire laisserait
        croire a un historique complet."""
        d = developpement_130(TRIANGLE)
        self.assertEqual(d['profondeur_disponible'], 2)
        self.assertEqual(d['profondeur_demandee_par_130'], 10)
        self.assertIn('DÉVELOPPEMENT PARTIEL', d['motif'])
        self.assertIn('dix ans', d['motif'])
        print(f"    OK Z3 : {d['profondeur_disponible']} annees disponibles "
              f"contre {d['profondeur_demandee_par_130']} demandees, limite "
              "nommee")

    def test_le_tableau_publie_ce_qui_est_observe(self):
        d = developpement_130(TRIANGLE)
        self.assertEqual(d['annees_survenance'], [2025, 2026])
        self.assertAlmostEqual(d['charge_cumulee'][2025][1], 1650.0, 6)
        print("    OK Z3b : le tableau publie la charge cumulee observee")


class Z4_LesRefus(unittest.TestCase):
    """Z4 — ce que le module refuse plutôt que de le fausser."""

    def test_un_triangle_vide_n_est_pas_un_passif_nul(self):
        with self.assertRaises(RefusMesure) as ctx:
            passif_sinistres_ctx([], _proj(), dispense_59b=True)
        self.assertEqual(ctx.exception.motif, MOTIF_AUCUNE_CELLULE)
        self.assertIn('Ran 0 tests', str(ctx.exception))
        print("    OK Z4 : triangle vide -> refus, jamais un passif nul")

    def test_des_paiements_superieurs_a_la_charge_sont_refuses(self):
        """La charge COMPREND les paiements ; l'inverse signale deux
        conventions melangees."""
        faux = (Cellule('MRH', 2025, 0, 900.0, 500.0),)
        with self.assertRaises(RefusMesure) as ctx:
            passif_sinistres_ctx(faux, _proj(), dispense_59b=True)
        self.assertEqual(ctx.exception.motif, MOTIF_TRIANGLE_INCOHERENT)
        self.assertIn('MRH', str(ctx.exception))
        print("    OK Z4b : paiements > charge -> refus, la cellule fautive "
              "est nommee")

    def test_une_projection_sans_METHODE_est_refusee(self):
        """⚠️ CHAIN LADDER ET BORNHUETTER-FERGUSON SUR LE MEME TRIANGLE NE
        DONNENT PAS LE MEME ULTIME. Un montant sans sa methode est
        invérifiable."""
        for kw in ({'methode': ''}, {'methode': 'A_RENSEIGNER'},
                   {'actuaire_resp': 'TBD'}, {'arrete': 'N/A'}):
            base = {'ultime': 3400.0, 'methode': 'Chain Ladder',
                    'actuaire_resp': 'Selasse Sekle', 'arrete': '2026-12-31'}
            base.update(kw)
            with self.assertRaises(RefusMesure) as ctx:
                declarer_projection(**base)
            self.assertEqual(ctx.exception.motif,
                             MOTIF_PROJECTION_NON_DECLAREE)
        print("    OK Z4c : projection sans methode, sans signataire ou sans "
              "arrete -> refus, y compris sur remplissage FICTIF")


class Z5_AucuneDependanceHorsDuChantier(unittest.TestCase):
    """Z5 — le pont vers le provisionnement n'existe pas, et c'est voulu."""

    def test_le_module_n_importe_ni_A7_ni_core(self):
        """⚠️ MESURE, PAS PRINCIPE. Le choix de la methode de projection est
        un JUGEMENT ACTUARIEL -- l'agent A7 en offre cinq -- et le module le
        recoit declare. Et dependre de `direction_non_vie/` condamnerait tout
        lot futur du chantier a la gate non-vie de 24 minutes.
        """
        import ast
        import inspect

        from normes.ifrs17.mesure import lic
        arbre = ast.parse(inspect.getsource(lic))
        mods = set()
        for n in ast.walk(arbre):
            if isinstance(n, ast.Import):
                mods |= {a.name.split('.')[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add((n.module or '').split('.')[0])
        for interdit in ('direction_non_vie', 'core', 'a7_provisionnement'):
            self.assertNotIn(interdit, mods, interdit)
        print(f"    OK Z5 : imports {sorted(mods)} — ni A7 ni core, la gate "
              "reste `normes` seule")


if __name__ == '__main__':
    unittest.main()
