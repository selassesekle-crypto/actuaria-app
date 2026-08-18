# =============================================================================
#  UN SCR NON CALCULE SE DIT — IL NE SE REMPLACE NI NE FAIT TOMBER LE RAPPORT
# =============================================================================
#
#  ⚠️ GATE : `py -m unittest discover -s direction_non_vie -t .`
#
#  ⚠️ DEUX DEFAUTS VIVAIENT DANS LA MEME EXPRESSION, EN TROIS EXEMPLAIRES
#  (contexte du LLM, HTML, Word) :
#
#      SCP = float(sc.get('scr_provisions',
#                         sc.get('scr_prov', BE * 0.30)) if sc else BE * 0.30)
#
#  · SCR ABSENT -> un chiffre FABRIQUE a 30 % du Best Estimate, publie sans
#    marque. Mesure : BE de 1 000 -> << SCR 300 EUR | Ratio SCR/BE 30,0 % >>.
#  · `scr_provisions` PRESENT A None -> `.get` ne prend jamais son repli,
#    `float(None)` leve, et le rapport ne se genere pas.
#
#  ⚠️⚠️ ET C'EST LE SECOND QUI COMPTE, PARCE QUE SA CAUSE EST L'INVERSE D'UN
#  DEFAUT. `None` est pose par `garde_fou_be_negatif` quand le Best Estimate
#  est NEGATIF : N4 y refuse d'inventer, marque l'absence, passe en ROUGE --
#  << marqueurs None + statut ROUGE, jamais de plancher silencieux >>. Le
#  renderer DEFAISAIT ce garde-fou en plantant dessus. La couche de calcul
#  faisait ce qu'il fallait ; la couche de rendu ne savait pas le rendre.
#
#  C'est la forme la plus forte du releve B2 : le module a le bon instrument
#  (`_f` et `_pct` publient deja un tiret sur None), et il etait court-circuite
#  en amont.
# =============================================================================

import unittest

from . import n5_rapport as _n5r

#: Les quatre etats possibles du bloc SCR, et ce que chacun doit publier.
BE = 1000.0
ETATS = (
    ('absent',            {'best_estimate': BE},                              None),
    ('vide',              {'best_estimate': BE, 'scr': {}},                    None),
    # ⚠️ L'ETAT QUE POSE `garde_fou_be_negatif` — celui qui faisait tomber.
    ('present_a_None',    {'best_estimate': BE,
                           'scr': {'scr_provisions': None}},                   None),
    ('calcule',           {'best_estimate': BE,
                           'scr': {'scr_provisions': 280.0}},                 280.0),
)


class S1_Le_SCR_Ne_Se_Fabrique_Plus(unittest.TestCase):
    """⚠️ 30 % DU BE ETAIT UNE CONVENTION PUBLIEE COMME UNE MESURE."""

    def test_les_quatre_etats_rendent_ce_qu_ils_doivent(self):
        for nom, n4, attendu in ETATS:
            self.assertEqual(_n5r._scr_publiable(n4.get('scr', {})), attendu,
                             f'etat {nom}')
        print('    OK S1-1 les quatre etats du SCR rendent la bonne valeur')

    def test_aucun_trentieme_pour_cent_ne_subsiste(self):
        # ⚠️ LA VALEUR FABRIQUEE NE DOIT PLUS APPARAITRE, quel que soit le BE.
        for nom, n4, attendu in ETATS:
            if attendu is not None:
                continue
            self.assertIsNone(_n5r._scr_publiable(n4.get('scr', {})),
                              f'{nom} rend encore une valeur')
            self.assertIsNone(_n5r._ratio_scr(None, BE))
        print('    OK S1-2 plus aucun SCR fabrique a 30 % du BE')

    def test_le_ratio_ne_se_calcule_pas_sans_scr(self):
        self.assertIsNone(_n5r._ratio_scr(None, BE))
        self.assertIsNone(_n5r._ratio_scr(280.0, 0))
        self.assertAlmostEqual(_n5r._ratio_scr(280.0, BE), 28.0)
        print('    OK S1-3 le ratio suit le SCR, il ne le supplee pas')


class S2_Le_Contexte_Du_LLM_Dit_Le_Tiret(unittest.TestCase):
    """Le prompt ne doit pas soumettre au modele un chiffre invente."""

    def test_les_trois_etats_non_calculables_donnent_un_tiret(self):
        for nom, n4, attendu in ETATS:
            txt = _n5r._construire_contexte({}, {}, n4, 'X', '30/06')
            ligne = next(x for x in txt.splitlines() if x.startswith('SCR='))
            if attendu is None:
                self.assertIn('—', ligne, f'etat {nom}')
                self.assertNotIn('300', ligne)
            else:
                self.assertIn('280', ligne)
        print('    OK S2-1 le contexte du LLM ne porte plus de SCR fabrique')


#: Tout ce que `garde_fou_be_negatif` met a None, d'un bloc. Au niveau du
#: module et non de la classe : un attribut de classe mutable demanderait un
#: `ClassVar`, et ce dict n'appartient pas plus a une classe qu'a une autre.
N4_GARDE = {'best_estimate': BE, 'risk_margin': None,
            'provisions_techniques_s2': None, 'reserve_p90': None,
            'scr': {'scr_provisions': None, 'ratio_scr_be': None}}


class S3_Le_Garde_Fou_BE_NEGATIF_Ne_Fait_Plus_Tomber_Le_Rapport(unittest.TestCase):
    """⚠️ LA VRAIE VICTIME : un etat que N4 marque CORRECTEMENT."""

    def test_le_html_se_genere(self):
        b = _n5r._build_blocks({}, {}, dict(N4_GARDE), '', 'aucune', 'X',
                               'C', '30/06', '18/08', 'A', 'cl', 'ROUGE', '')
        self.assertIn('SCR Provisions', b['kpi_grid'])
        self.assertIn('—', b['kpi_grid'])
        print('    OK S3-1 le HTML se genere sur un BE negatif')

    def test_le_kpi_risk_margin_ne_leve_plus(self):
        # ⚠️ `risk_margin` PRESENT A None faisait lever `None > 0`, deux lignes
        # apres le SCR. Meme garde-fou, meme chute.
        b = _n5r._build_blocks({}, {}, dict(N4_GARDE), '', 'aucune', 'X',
                               'C', '30/06', '18/08', 'A', 'cl', 'ROUGE', '')
        self.assertNotIn('Provisions Tech. S2', b['kpi_grid'])
        print('    OK S3-2 la carte KPI ne tombe plus sur risk_margin=None')


if __name__ == '__main__':
    unittest.main(verbosity=2)
