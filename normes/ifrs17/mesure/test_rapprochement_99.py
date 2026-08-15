# -*- coding: utf-8 -*-
"""Tests N1 — §99 b) : le rapprochement boucle sur le bilan, ou il refuse.

⚠️ GATE : `py -m unittest discover -s normes -t .`

⚠️ LE TEST QUI PORTE CE MODULE EST `test_LE_CAS_QUE_LE_NET_LAISSERAIT_
PASSER` : sans lui, on aurait un contrôle qui se croit fort et qui boucle
trivialement.
"""
import unittest

from normes.ifrs17.mesure.bilan import SoldeGroupe, etat_situation_financiere
from normes.ifrs17.mesure.declaration import ContexteEvaluation
from normes.ifrs17.mesure.lrc_paa import RefusMesure
from normes.ifrs17.mesure.rapprochement_99 import (
    MOTIF_ARTICULATION_99B,
    MOTIF_AUCUN_SOLDE_RAPPROCHE,
    MOTIF_CEDE_SANS_BILAN,
    RESERVE_DU_CEDE,
    verifier_articulation_99b,
)

#: ⚠️ Les deux natures viennent du magasin, et elles sont PASSÉES en
#: paramètre : ce module n'importe pas le socle.
EMIS = 'EMIS'
CEDE = 'REASSURANCE_DETENUE'

PTF = ('DO', 'MRH', 'GAV')
CONTEXTE = ContexteEvaluation(arrete='2026-12-31', portefeuilles=PTF)

#: DO et GAV sont des passifs, MRH un actif — une créance de prime non
#: encaissée, cas réel que `bilan` nomme.
MESURE = (SoldeGroupe('DO', 'DO|AUTRES|2026', 1000.0),
          SoldeGroupe('MRH', 'MRH|AUTRES|2026', -300.0),
          SoldeGroupe('GAV', 'GAV|AUTRES|2026', 250.0))


def _bilan(soldes=MESURE):
    return etat_situation_financiere(list(soldes), CONTEXTE)


def _verifier(rapprochement=MESURE, bilan=None, nature=EMIS):
    return verifier_articulation_99b(
        soldes_du_rapprochement=list(rapprochement),
        bilan=bilan if bilan is not None else _bilan(),
        nature_du_rapprochement=nature, nature_emise=EMIS)


class T1_LArticulationExigeeParLe99b(unittest.TestCase):
    """⚠️ §99 b) EXIGE UNE ÉGALITÉ, pas une vraisemblance."""

    def test_deux_etats_qui_disent_la_meme_chose_bouclent(self):
        m = _verifier()
        self.assertIn('boucle sur', m)
        self.assertIn('3 portefeuille(s)', m)
        print("    OK N1 : rapprochement et bilan concordent sur les DEUX "
              "totaux")

    def test_un_ecart_sur_un_seul_total_est_refuse(self):
        faux = (SoldeGroupe('DO', 'DO|AUTRES|2026', 1500.0),
                SoldeGroupe('MRH', 'MRH|AUTRES|2026', -300.0),
                SoldeGroupe('GAV', 'GAV|AUTRES|2026', 250.0))
        with self.assertRaises(RefusMesure) as e:
            _verifier(faux)
        self.assertEqual(e.exception.motif, MOTIF_ARTICULATION_99B)
        self.assertIn('PASSIFS', str(e.exception))
        self.assertIn('+500.00', str(e.exception))

    def test_LE_CAS_QUE_LE_NET_LAISSERAIT_PASSER(self):
        """⚠️⚠️ LE TEST QUI JUSTIFIE LES DEUX TOTAUX. Un portefeuille passé
        du bon côté à l'autre laisse la somme signée INCHANGÉE : le net
        boucle, et les deux lignes sont fausses. C'est la faute que `bilan`
        refuse déjà entre portefeuilles — « un bilan dont le total est juste
        et dont les deux lignes sont fausses, une erreur qu'aucun contrôle
        d'équilibre ne verrait, puisque l'équilibre tient »."""
        # MRH passe d'actif (-300) à passif (+300) et GAV compense.
        faux = (SoldeGroupe('DO', 'DO|AUTRES|2026', 1000.0),
                SoldeGroupe('MRH', 'MRH|AUTRES|2026', 300.0),
                SoldeGroupe('GAV', 'GAV|AUTRES|2026', -350.0))
        net_vrai = sum(s.valeur_comptable for s in MESURE)
        net_faux = sum(s.valeur_comptable for s in faux)
        self.assertAlmostEqual(net_vrai, net_faux, 6,
                               "le net doit boucler : c'est tout le piege")
        with self.assertRaises(RefusMesure) as e:
            _verifier(faux)
        self.assertEqual(e.exception.motif, MOTIF_ARTICULATION_99B)
        self.assertIn('ET LE NET, LUI, BOUCLE', str(e.exception))
        print(f"    OK N1b : net identique ({net_vrai:.0f}) des deux cotes, "
              "les DEUX totaux faux -> REFUSE")

    def test_le_motif_dit_que_la_comparaison_n_est_PAS_sur_le_net(self):
        m = _verifier()
        self.assertIn('JAMAIS SUR LE NET', m)
        self.assertIn('mauvais côté', m)

    def test_un_rapprochement_VIDE_est_refuse(self):
        """⚠️ Un accord constaté sur un ensemble vide le serait
        trivialement — la faute de « Ran 0 tests » en sortant 0."""
        with self.assertRaises(RefusMesure) as e:
            _verifier(())
        self.assertEqual(e.exception.motif, MOTIF_AUCUN_SOLDE_RAPPROCHE)
        self.assertIn('Ran 0 tests', str(e.exception))

    def test_la_tolerance_est_celle_d_une_IDENTITE(self):
        """⚠️ Ces deux totaux sont les MÊMES montants lus par deux chemins :
        un centime d'écart n'est pas un arrondi, c'est une divergence."""
        presque = (SoldeGroupe('DO', 'DO|AUTRES|2026', 1000.01),
                   SoldeGroupe('MRH', 'MRH|AUTRES|2026', -300.0),
                   SoldeGroupe('GAV', 'GAV|AUTRES|2026', 250.0))
        with self.assertRaises(RefusMesure):
            _verifier(presque)


class T2_LeCedeNePeutPasBOUCLER(unittest.TestCase):
    """⚠️⚠️ §98 EXIGE UN RAPPROCHEMENT SÉPARÉ POUR LA RÉASSURANCE DÉTENUE, ET
    §78 c) ET d) NE SONT PAS CONSTRUITS. Le faire boucler sur un bilan qui ne
    le porte pas donnerait un zéro qui passerait pour un accord."""

    def test_le_cede_est_REFUSE_et_non_boucle_a_zero(self):
        with self.assertRaises(RefusMesure) as e:
            _verifier(nature=CEDE)
        self.assertEqual(e.exception.motif, MOTIF_CEDE_SANS_BILAN)
        self.assertIn('§78 c) et d)', str(e.exception))
        print("    OK N1c : le cede est REFUSE -- pas d'accord constate sur "
              "une ligne absente")

    def test_le_refus_dit_que_LA_MESURE_EXISTE_et_que_c_est_la_LIGNE_qui_manque(
            self):
        """⚠️ La prémisse compte autant que la conclusion : ce n'est pas la
        réassurance qui n'est pas mesurée, c'est la ligne de bilan qui
        n'existe pas. Le dépôt a déjà payé cette confusion une fois."""
        self.assertIn("CE N'EST PAS LA MESURE QUI MANQUE", RESERVE_DU_CEDE)
        self.assertIn('§60-70A', RESERVE_DU_CEDE)

    def test_la_reserve_descend_AUSSI_avec_un_accord_reussi(self):
        """⚠️ Un motif qui ne dit sa portée qu'en cas d'échec se fait
        surévaluer en cas de succès."""
        self.assertIn(RESERVE_DU_CEDE, _verifier())


class Z_LaRegleDu78_N_EXISTE_QU_UNE_FOIS(unittest.TestCase):
    """⚠️⚠️ COMPARER DEUX ÉTATS EXIGE DE LES VENTILER AVEC LA MÊME RÈGLE.

    Deux règles proches feraient lire une divergence de MÉTHODE comme une
    divergence de MONTANTS — et ce dépôt combat les secondes sources depuis
    les huit sources de taux.
    """

    def test_ce_module_ne_recopie_pas_la_ventilation_du_bilan(self):
        import ast
        import inspect

        from normes.ifrs17.mesure import rapprochement_99
        src = inspect.getsource(rapprochement_99)
        arbre = ast.parse(src)
        importe = {a.name for n in ast.walk(arbre)
                   if isinstance(n, ast.ImportFrom) for a in n.names}
        self.assertIn('ventiler_par_cote', importe,
                      "la ventilation du §78 doit être IMPORTÉE, pas refaite")
        # ⚠️ ET LE CONTRÔLE SE FAIT SUR L'AST : chercher « est_actif » dans le
        # texte trouverait la phrase qui dit qu'on ne le recalcule pas.
        noms = {n.attr for n in ast.walk(arbre)
                if isinstance(n, ast.Attribute)}
        self.assertNotIn('est_actif', noms,
                         "ce module reventile lui-même : seconde source")
        print("    OK N1z : la regle du §78 est importee, jamais recopiee")


if __name__ == '__main__':
    unittest.main(verbosity=2)
