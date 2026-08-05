# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — A7  ·  GARDE-FOU D'UNITÉ SUR LES COURBES DE TAUX
=============================================================================

Les fichiers EIOPA publient les taux en DÉCIMAL — 0,02826 pour 2,826 %. Ce
module attend des POURCENTS et divise par cent. Un fichier EIOPA importé tel
quel produirait donc une courbe CENT FOIS TROP BASSE.

⚠️ C'EST LE SEUL DES TROIS OBSTACLES À UN IMPORT BRUT QUI ÉCHOUERAIT EN
SILENCE. Les deux autres s'arrêtent bruyamment :
   · `pd.read_excel` sans `sheet_name` lit `Main_Menu`, pas `RFR_spot_no_VA` ;
   · l'onglet n'a pas d'en-tête exploitable — pays en ligne 2, paramètres en
     lignes 4 à 10, taux à partir de la ligne 11.
Une courbe cent fois trop basse, elle, se calculerait sans un mot et
n'apparaîtrait que dans la Risk Margin.

⚠️ ET LE MÊME PIÈGE EXISTE SUR LA SAISIE MANUELLE — le relevé exhaustif l'a
trouvé, ma liste ne le contenait pas. `get_courbe_taux_plat(0.03)` rendait une
courbe à 0,030 % au lieu de 3 %. L'erreur a été commise pendant la conception
de ce garde-fou, sur cette fonction même.
"""

import io
import unittest

from direction_non_vie.provisionnement.a7_provisionnement.config.rfr_eiopa import (
    TAUX_MIN_PLAUSIBLE_PCT, get_courbe_depuis_excel, get_courbe_taux_plat)

try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:                                        # pragma: no cover
    PANDAS_OK = False

#: Courbe EUR de fin 2020 — le point bas historique de la zone euro, négative
#: jusque vers quinze ans. C'est le cas le plus défavorable au garde-fou :
#: une courbe LÉGITIME dont les taux sont proches de zéro.
_EUR_2020 = {1: -0.60, 5: -0.55, 10: -0.25, 15: -0.02, 20: 0.15, 30: 0.35,
             50: 1.30, 90: 2.60, 150: 3.15}


def _classeur(maturites, taux):
    """Un classeur Excel au format que `get_courbe_depuis_excel` attend."""
    tampon = io.BytesIO()
    pd.DataFrame({'maturite': list(maturites),
                  'taux_pct': list(taux)}).to_excel(tampon, index=False)
    return tampon.getvalue()


class TGARDE_Unite(unittest.TestCase):

    def setUp(self):
        if not PANDAS_OK:
            self.skipTest("pandas absent — pas d'import Excel à exercer")

    # ── le piège lui-même ────────────────────────────────────────────────
    def test_une_courbe_en_decimal_est_refusee(self):
        mats = sorted(_EUR_2020)
        decimal = [_EUR_2020[m] / 100.0 for m in mats]
        r = get_courbe_depuis_excel(_classeur(mats, decimal))
        self.assertEqual(r['type'], 'erreur')
        self.assertIn('décimaux', r['erreur'])
        print(f"    OK GARDE-1a une courbe en décimal est refusée "
              f"(max {max(abs(x) for x in decimal):.5f} < "
              f"{TAUX_MIN_PLAUSIBLE_PCT})")

    def test_le_message_dit_quoi_faire(self):
        """⚠️ REFUSER NE SUFFIT PAS. Un actuaire bloqué sans consigne rouvrira
        le même fichier et réessaiera. Le message doit nommer l'unité attendue,
        expliquer d'où vient l'écart, et donner l'issue de secours."""
        r = get_courbe_depuis_excel(_classeur([1, 10, 30],
                                              [0.028, 0.031, 0.033]))
        msg = r['erreur']
        self.assertIn('POURCENTAGE', msg)
        self.assertIn('100', msg)
        self.assertIn('EIOPA', msg)
        self.assertIn('taux manuel', msg)
        print("    OK GARDE-1b le message nomme l'unité, l'origine de l'écart "
              "et l'issue de secours")

    # ── ce qui doit passer, et c'est le vrai test du seuil ───────────────
    def test_une_courbe_legitime_en_pourcentage_passe(self):
        mats = sorted(_EUR_2020)
        r = get_courbe_depuis_excel(
            _classeur(mats, [_EUR_2020[m] for m in mats]))
        self.assertEqual(r['type'], 'fichier_excel')
        self.assertAlmostEqual(r['taux_fn'](10), -0.0025, places=6)
        print("    OK GARDE-2a la courbe EUR fin 2020, négative jusqu'à 15 "
              "ans, passe sans réserve")

    def test_une_courbe_legitime_tronquee_aux_taux_negatifs_passe(self):
        """⚠️ LE CAS QUI A DÉCIDÉ DU SEUIL, et il tient à la VALEUR ABSOLUE.

        Un actuaire peut n'importer que les maturités courtes. En 2020 elles
        étaient toutes négatives : le maximum SIGNÉ vaut alors −0,25, sous
        n'importe quel seuil. C'est le maximum en MODULE — 0,60 — qui
        distingue cette courbe légitime des 0,034 d'un fichier en décimal.
        """
        courtes = [m for m in sorted(_EUR_2020) if m <= 10]
        r = get_courbe_depuis_excel(
            _classeur(courtes, [_EUR_2020[m] for m in courtes]))
        self.assertEqual(r['type'], 'fichier_excel',
                         "une courbe légitime en régime négatif est refusée : "
                         "le seuil est trop haut")
        print("    OK GARDE-2b une courbe tronquée à 10 ans, entièrement "
              "négative, passe — c'est le module qui la sauve")

    def test_le_seuil_separe_les_deux_extremes_avec_marge(self):
        """Le seuil est calibré, pas choisi : facteur ~4,4 de part et d'autre."""
        self.assertGreater(TAUX_MIN_PLAUSIBLE_PCT, 0.0337 * 2,
                           "trop bas : un fichier EIOPA en décimal passerait")
        self.assertLess(TAUX_MIN_PLAUSIBLE_PCT, 0.60 / 2,
                        "trop haut : une courbe légitime en régime négatif "
                        "serait refusée")
        print(f"    OK GARDE-2c seuil {TAUX_MIN_PLAUSIBLE_PCT} : au-dessus de "
              f"0,0337 (décimal) et au-dessous de 0,60 (légitime serré)")

    # ── la saisie manuelle, second point d'entrée ────────────────────────
    def test_la_saisie_manuelle_est_gardee_aussi(self):
        r = get_courbe_taux_plat(0.03)
        self.assertEqual(r['type'], 'erreur')
        self.assertIn('POURCENTAGE', r['erreur'])
        ok = get_courbe_taux_plat(3.0)
        self.assertEqual(ok['type'], 'taux_plat')
        self.assertAlmostEqual(ok['taux_fn'](10), 0.03, places=6)
        print("    OK GARDE-3a `get_courbe_taux_plat(0.03)` est refusé, "
              "`(3.0)` passe et vaut bien 3 %")

    def test_un_taux_nul_assume_reste_permis(self):
        """Actualiser à zéro est un choix, pas une erreur d'unité."""
        r = get_courbe_taux_plat(0.0)
        self.assertEqual(r['type'], 'taux_plat')
        self.assertEqual(r['taux_fn'](10), 0.0)
        print("    OK GARDE-3b un taux nul assumé passe : ce n'est pas une "
              "erreur d'unité")

    def test_le_refus_ne_laisse_jamais_sans_courbe(self):
        """Un refus doit dégrader vers la courbe embarquée, jamais vers rien :
        le calcul de la Risk Margin ne peut pas s'arrêter là."""
        for r in (get_courbe_taux_plat(0.03),
                  get_courbe_depuis_excel(_classeur([1, 10], [0.02, 0.03]))):
            self.assertIn('taux_fn', r)
            self.assertGreater(r['taux_fn'](10), 0.0)
        print("    OK GARDE-3c un refus rend toujours une courbe utilisable — "
              "l'embarquée — et jamais `None`")


if __name__ == '__main__':
    unittest.main(verbosity=2)
