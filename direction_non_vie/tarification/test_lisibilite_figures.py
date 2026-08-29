"""Controles positifs — lot 4.3 : `charts/C9` et `charts/C10`.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
`charts/C9` — DEUX DECILES DIFFERENTS SE LISAIENT PAREIL. L'ancre mediane du
gradient etait un TURQUOISE de luminance **0,3854**, plus CLAIR que les deux
extremites (0,1269 et 0,2514). La rampe montait jusqu'a D5 puis redescendait :

    luminance D1->D10 : 0.13 0.17 0.22 0.28 0.35 0.34 0.28 0.24 0.23 0.25
    inversions = 4        ecart minimal entre voisins = 0,0035

⚠️ LES DEUX EXTREMITES NE CHANGENT PAS : elles portent le sens (bleu = bas
risque, orange = haut). Seule l'ancre mediane bouge, et vers une luminance
COMPRISE entre les deux -- c'est la condition de la monotonie, pas un gout.

⚠️⚠️ ET LE REMEDE N'EST PAS L'ANCRE, C'EST L'ECHANTILLONNAGE. Mesure : avec la
bonne ancre mais un echantillonnage regulier en `t`, l'ecart minimal ne monte
qu'a 0,0044 -- l'interpolation est lineaire en RGB, pas en luminance. En
echantillonnant a LUMINANCE REGULIERE : **0 inversion, ecart minimal 0,0109**,
pour un maximum theorique de 0,0138.

`charts/C10` — L'AMBRE DU RAG ETAIT L'OR DES AXES. Le point AMBRE prenait
`COULEURS['or_accent']` (#D4AF37), la teinte EXACTE des lignes de bande :
ecart de teinte 0°, contraste 1,00.

⚠️⚠️ ET LE CONSTAT ETAIT PLUS LARGE QUE SON LIBELLE. Mesure au site : les
TROIS couleurs contournaient la source RAG -- VERT prenait `ligne_predite`
(#00E5A0), ROUGE un litteral `rgba(240,85,35,0.95)`. Trois definitions locales
que le lot de la charte n'avait pas atteintes.

⚠️ ET LA COULEUR SEULE NE SUFFIT PAS -- mesure, pas supposition : VERT et
AMBRE ont un contraste mutuel de **1,04**, la MEME luminance. `SYMBOLE_RAG`
existait dans la source depuis le lot de la charte et n'etait employe NULLE
PART. Une figure a POINTS est exactement son usage.
"""

from __future__ import annotations

import unittest

from core.charts_tarif import (
    _GRAD_ANCRES,
    FOND_SOMBRE,
    SYMBOLE_RAG,
    _couleur_gradient,
    _gradient_ordonne,
    _luminance_rgba,
    chart_walkforward_ae,
    contraste,
    couleur_rag,
)

_BANDES = {'bande_acceptable': (0.90, 1.10), 'bande_stricte': (0.95, 1.05)}


class TestGradientMonotone(unittest.TestCase):
    """`charts/C9` — une échelle ordonnée se lit dans l'ordre."""

    def test_les_ancres_sont_monotones_en_luminance(self):
        """⚠️ LA CONDITION DE LA MONOTONIE, ÉPINGLÉE À LA SOURCE.

        L'échantillonnage par dichotomie SUPPOSE une luminance croissante. Si
        une ancre repassait sous la précédente, la recherche rendrait n'importe
        quoi — sans lever. *Un mécanisme qui suppose une propriété doit
        l'exiger.*
        """
        from core.charts_tarif import _luminance
        lums = [_luminance(f'#{c[0]:02X}{c[1]:02X}{c[2]:02X}')
                for _, c in _GRAD_ANCRES]
        self.assertEqual(
            lums, sorted(lums),
            f'les ancres ne sont plus monotones en luminance : {lums}')
        self.assertLess(lums[0], lums[1], 'ancre médiane sous la basse')
        self.assertLess(lums[1], lums[2], 'ancre médiane au-dessus de la haute')
        print(f"    OK C9-1 ancres monotones : "
              f"{' < '.join(f'{x:.4f}' for x in lums)}")

    def test_zero_inversion_sur_dix_deciles(self):
        """⚠️⚠️ LE TEST QUI FERME LE CONSTAT — la mesure d'origine, rejouée."""
        lums = [_luminance_rgba(c) for c in _gradient_ordonne(10)]
        inversions = [i for i in range(1, 10) if lums[i] < lums[i - 1]]
        self.assertEqual(
            inversions, [],
            f'{len(inversions)} inversion(s) de luminance : {inversions} — '
            f'deux déciles différents se lisent pareil')
        print("    OK C9-2 0 inversion sur 10 déciles (relevé : 4)")

    def test_l_ecart_minimal_depasse_celui_du_releve(self):
        """⚠️ La monotonie ne suffit pas : deux déciles séparés de 0,0001
        seraient monotones ET indiscernables.

        Le relevé mesurait 0,0035 et visait 0,0086. Le maximum théorique,
        avec ces extrémités, est (haut − bas)/9 = 0,0138.
        """
        lums = [_luminance_rgba(c) for c in _gradient_ordonne(10)]
        ecart = min(lums[i] - lums[i - 1] for i in range(1, 10))
        self.assertGreater(ecart, 0.0086,
                           f'écart minimal {ecart:.4f} — sous la cible du relevé')
        theorique = (lums[-1] - lums[0]) / 9
        self.assertGreater(ecart, theorique * 0.75,
                           'l\'échantillonnage n\'est plus régulier en luminance')
        print(f"    OK C9-3 écart minimal {ecart:.4f} (relevé 0,0035 · cible "
              f"0,0086 · maximum {theorique:.4f})")

    def test_les_deux_EXTREMITES_ne_changent_pas(self):
        """⚠️⚠️ SECOND SENS — elles portent le SENS, pas l'esthétique.

        Bleu = bas risque, orange = haut. Les déplacer changerait la lecture du
        graphique, pas seulement sa lisibilité.
        """
        self.assertEqual(_GRAD_ANCRES[0][1], (30, 100, 180), 'extrémité basse')
        self.assertEqual(_GRAD_ANCRES[-1][1], (240, 85, 35), 'extrémité haute')
        print("    OK C9-4 extrémités inchangées : bleu profond → orange danger")

    def test_le_gradient_reste_defini_sur_un_seul_decile(self):
        """⚠️ Le cas dégénéré : `n = 1` ne doit ni lever ni diviser par zéro."""
        self.assertEqual(len(_gradient_ordonne(1)), 1)
        self.assertTrue(_couleur_gradient(0.5).startswith('rgba('))
        print("    OK C9-5 n=1 : une couleur, aucune division par zéro")


class TestPointRAGLisible(unittest.TestCase):
    """`charts/C10` — un point AMBRE se lit comme un avertissement."""

    def _marqueur(self, ae):
        fig = chart_walkforward_ae(
            [{'annee': 2020 + i, 'ae_ratio': v} for i, v in enumerate(ae)],
            **_BANDES)
        for tr in fig.data:
            marqueur = getattr(tr, 'marker', None)
            if marqueur is not None and getattr(marqueur, 'symbol', None):
                return marqueur
        self.fail('aucun marqueur de points trouvé')

    def test_les_trois_couleurs_viennent_de_la_SOURCE(self):
        """⚠️⚠️ LE TEST QUI FERME LE CONSTAT — et il est plus large que lui.

        Le relevé ne visait que l'AMBRE ; les TROIS contournaient la source.
        """
        marqueur = self._marqueur([1.00, 1.08, 1.30])
        self.assertEqual(
            list(marqueur.color),
            [couleur_rag(s, FOND_SOMBRE) for s in ('VERT', 'AMBRE', 'ROUGE')])
        print(f"    OK C10-1 les 3 couleurs lisent la source : "
              f"{list(marqueur.color)}")

    def test_l_ambre_n_est_plus_l_or_MAIS_la_couleur_ne_suffit_pas(self):
        """⚠️⚠️ CE TEST A RÉFUTÉ UNE ATTENTE QUE J'AVAIS INVENTÉE.

        J'avais écrit `assertGreater(contraste, 1.10)`, en supposant que passer
        de l'or `#D4AF37` à l'ambre RAG `#F39C12` séparerait le point du décor.
        **Mesuré : le contraste reste à 1,04.** La teinte bouge de 0° à 9,1° ;
        la LUMINANCE, elle, ne bouge pratiquement pas.

        Pire -- mesuré aussi : le **VERT** `#2ECC71` est à **1,00** contre l'or.
        *Exactement la même luminance que le décor.*

        > **La couleur ne ferme pas ce constat. Le SYMBOLE le ferme.**

        Ce test épingle donc les deux faits ensemble : l'or a bien disparu du
        point (la partie << définition locale >> du constat), ET la couleur ne
        suffit pas à l'en distinguer -- ce qui rend le second canal
        NÉCESSAIRE, pas décoratif.
        """
        marqueur = self._marqueur([1.08])
        self.assertNotIn('D4AF37', str(marqueur.color[0]).upper(),
                         "le point AMBRE porte encore l'or des axes")
        ecart = contraste(couleur_rag('AMBRE', FOND_SOMBRE), '#D4AF37')
        self.assertLess(
            ecart, 1.10,
            "ambre et or se séparent désormais par la luminance : la "
            "justification du second canal a changé, re-motiver ce test")
        vert_or = contraste(couleur_rag('VERT', FOND_SOMBRE), '#D4AF37')
        self.assertLess(vert_or, 1.10)
        print(f"    OK C10-2 l'or a quitté le point, MAIS ambre/or reste à "
              f"{ecart} et vert/or à {vert_or} : la couleur ne suffit pas")

    def test_le_SECOND_CANAL_est_employe(self):
        """⚠️⚠️ LA COULEUR SEULE NE SUFFIT PAS, ET C'EST MESURÉ.

        VERT et AMBRE ont un contraste mutuel de 1,04 — la même luminance. En
        niveaux de gris les deux statuts fusionnent. `SYMBOLE_RAG` existait
        dans la source et n'était employé nulle part.
        """
        mutuel = contraste(couleur_rag('VERT', FOND_SOMBRE),
                           couleur_rag('AMBRE', FOND_SOMBRE))
        self.assertLess(mutuel, 1.10,
                        'VERT et AMBRE se séparent désormais par la luminance : '
                        'ce test doit être re-motivé')
        marqueur = self._marqueur([1.00, 1.08, 1.30])
        self.assertEqual(
            list(marqueur.symbol),
            [SYMBOLE_RAG[s] for s in ('VERT', 'AMBRE', 'ROUGE')])
        self.assertEqual(len(set(marqueur.symbol)), 3,
                         'les trois statuts partagent une silhouette')
        print(f"    OK C10-3 contraste mutuel VERT/AMBRE = {mutuel} : le "
              f"second canal {list(marqueur.symbol)} les sépare par la FORME")

    def test_les_lignes_de_DECOR_gardent_l_or(self):
        """⚠️⚠️ SECOND SENS — on ne repeint pas ce qui n'est pas un statut.

        Les lignes de bande et l'axe sont du DÉCOR : l'or y est légitime. Un
        correctif qui les aurait repeintes aurait échangé un défaut contre un
        autre.
        """
        fig = chart_walkforward_ae([{'annee': 2020, 'ae_ratio': 1.0}], **_BANDES)
        lignes = [s for s in (fig.layout.shapes or ())
                  if getattr(s, 'type', '') == 'line']
        couleurs = {str(getattr(s.line, 'color', '')).upper() for s in lignes}
        self.assertTrue(any('D4AF37' in c for c in couleurs),
                        'les lignes de bande ont perdu l\'or du décor')
        print("    OK C10-4 le décor garde l'or : seul le STATUT a changé")


if __name__ == '__main__':
    unittest.main()
