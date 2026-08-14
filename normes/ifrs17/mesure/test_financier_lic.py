# -*- coding: utf-8 -*-
"""Tests AA1 — le mouvement financier du LIC (§87 a).

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️ AUCUN ORACLE. Aucune source publiée disponible ne ventile un mouvement
financier de passif sinistres entre effet du temps et effet des taux. Le
seul poste exige par la norme est le TOTAL ; la ventilation est une
information de gestion, et elle est UNIQUE ici faute d'une quatrieme
valorisation.
"""
import unittest

from normes.ifrs17.mesure.financier_lic import (
    CONVENTION,
    MOTIF_FLUX_PAYES_NEGATIFS,
    MOTIF_VALEUR_NEGATIVE,
    TEMPS_PUIS_TAUX,
    decomposer,
)
from normes.ifrs17.mesure.lrc_paa import RefusMesure

#: Un cas ou les taux ONT bouge -- sinon l'effet de taux serait nul et le
#: test ne distinguerait rien.
CAS = {'valeur_ouverture': 1000.0,
       'valeur_cloture_taux_ouverture': 830.0,   # deroule, taux d'ouverture
       'valeur_cloture_taux_cloture': 845.0,     # les taux ont BAISSE
       'flux_payes': 200.0}


class AA1_LaVentilationEstUNIQUE(unittest.TestCase):
    """AA1 — pas de choix, et c'est le résultat d'une correction."""

    def test_les_deux_composantes_somment_au_total(self):
        m = decomposer(**CAS)
        attendu = (CAS['valeur_cloture_taux_cloture'] + CAS['flux_payes']
                   - CAS['valeur_ouverture'])
        self.assertAlmostEqual(m.total, attendu, 9)
        self.assertAlmostEqual(m.desactualisation + m.effet_taux, m.total, 9)
        print(f"    OK AA1 : desactualisation {m.desactualisation:+.2f} + "
              f"effet de taux {m.effet_taux:+.2f} = total {m.total:+.2f}")

    def test_AUCUN_parametre_d_ordre_n_est_offert(self):
        """⚠️⚠️ CE TEST VERROUILLE UNE CORRECTION. Une premiere version
        offrait deux << conventions >> declarables ; elles rendaient les
        MEMES deux nombres, parce qu'avec trois valorisations la ventilation
        est UNIQUE. Le mecanisme existait pour un choix qui n'existait pas.

        Offrir un choix fictif est pire que n'en offrir aucun : le lecteur
        croit avoir arbitre.
        """
        import inspect
        params = set(inspect.signature(decomposer).parameters)
        self.assertNotIn('ordre', params)
        self.assertEqual(params, {'valeur_ouverture',
                                  'valeur_cloture_taux_ouverture',
                                  'valeur_cloture_taux_cloture',
                                  'flux_payes'})
        print(f"    OK AA1b : aucun parametre d'ordre — {len(params)} "
              "entrees, une seule ventilation possible")

    def test_le_partage_alternatif_est_NOMME_comme_non_offert(self):
        """⚠️ IL EXISTE, ET IL EXIGE UNE QUATRIEME VALORISATION. Le taire
        laisserait croire que la ventilation rendue est la seule pensable."""
        m = decomposer(**CAS)
        self.assertIn('QUATRIÈME', m.motif)
        self.assertIn("n'est donc PAS offert", m.motif)
        self.assertEqual(m.ordre, TEMPS_PUIS_TAUX)
        print("    OK AA1c : le partage alternatif est nomme, et dit non "
              "offert faute d'une quatrieme valorisation")


class AA2_LesEffetsSeDistinguent(unittest.TestCase):
    """AA2 — ce que la ventilation dit, quand elle dit quelque chose."""

    def test_sans_mouvement_de_taux_l_effet_de_taux_est_NUL(self):
        """Temoin : si la courbe n'a pas bouge, tout le mouvement est du
        deroulement."""
        cas = dict(CAS, valeur_cloture_taux_cloture=830.0)   # = taux ouverture
        m = decomposer(**cas)
        self.assertAlmostEqual(m.effet_taux, 0.0, 9)
        self.assertAlmostEqual(m.desactualisation, m.total, 9)
        print(f"    OK AA2 : courbe inchangee -> effet de taux nul, tout le "
              f"mouvement ({m.total:+.2f}) est du deroulement")

    def test_une_baisse_de_taux_AUGMENTE_le_passif(self):
        """⚠️ ACTUALISER MOINS FORT LAISSE UN PASSIF PLUS GROS. Un effet de
        taux positif sur une baisse est le signe attendu ; l'inverse
        signalerait une convention retournee."""
        m = decomposer(**CAS)   # 845 > 830
        self.assertGreater(m.effet_taux, 0)
        print(f"    OK AA2b : baisse de taux -> effet {m.effet_taux:+.2f}, "
              "le passif augmente")

    def test_la_convention_est_PUBLIEE_avec_le_resultat(self):
        """⚠️ UNE VENTILATION SANS SA CONVENTION N'EST PAS COMPARABLE."""
        m = decomposer(**CAS)
        self.assertIn('ne prescrit AUCUN partage', m.motif)
        self.assertIn('Seul le TOTAL est invariant', CONVENTION)
        self.assertIn('information de', m.motif)
        print("    OK AA2c : la convention et sa portee sont publiees avec "
              "le resultat")


class AA3_LesRefus(unittest.TestCase):
    """AA3 — ce que le module refuse plutôt que de le fausser."""

    def test_des_flux_payes_negatifs_sont_refuses(self):
        with self.assertRaises(RefusMesure) as ctx:
            decomposer(**dict(CAS, flux_payes=-10.0))
        self.assertEqual(ctx.exception.motif, MOTIF_FLUX_PAYES_NEGATIFS)
        print("    OK AA3b : flux payes negatifs -> refus, convention "
              "d'appel signalee")

    def test_une_valorisation_negative_est_refusee(self):
        for cle in ('valeur_ouverture', 'valeur_cloture_taux_cloture'):
            with self.assertRaises(RefusMesure) as ctx:
                decomposer(**dict(CAS, **{cle: -1.0}))
            self.assertEqual(ctx.exception.motif, MOTIF_VALEUR_NEGATIVE)
            self.assertIn(cle, str(ctx.exception))
        print("    OK AA3c : valorisation negative -> refus, le champ fautif "
              "est nomme")


class AA4_AucuneSecondeRegleDActualisation(unittest.TestCase):
    """AA4 — ce module décompose, il ne valorise pas."""

    def test_il_ne_reevalue_rien_lui_meme(self):
        """⚠️ LES TROIS VALORISATIONS VIENNENT DE `flux_execution`, avec ses
        courbes declarees et signees. Les recalculer ici ferait de ce module
        un SECOND lieu ou vit la regle d'actualisation -- et deux lieux
        divergent toujours."""
        import ast
        import inspect

        from normes.ifrs17.mesure import financier_lic
        src = inspect.getsource(financier_lic)
        self.assertNotIn('** ', src.replace('**kw', ''))   # aucune puissance
        arbre = ast.parse(src)
        mods = set()
        for n in ast.walk(arbre):
            if isinstance(n, ast.ImportFrom):
                mods.add((n.module or '').split('.')[0])
        self.assertEqual(mods, {'typing', 'normes'})
        print("    OK AA4 : aucune actualisation recalculee, aucune "
              "dependance hors du chantier")


if __name__ == '__main__':
    unittest.main()
