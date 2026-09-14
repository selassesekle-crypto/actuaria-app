r"""
==============================================================================
  UNE FIGURE NOMME LA GRANDEUR QU'ELLE MONTRE
==============================================================================

⚠️⚠️ `D3` -- REPORT DU ROUND 4, CONFIRME LE 14/09/2026.
`chart_distribution_predictions` portait `'Prime predite ({unite})'` EN
DUR sur son axe des abscisses, et formatait ses quantiles a ZERO
decimale. Or elle est appelee -- site VIVANT, `a3_glm/agent.py:3029` --
avec `unite=''` et le titre << Distribution des FREQUENCES predites >>.

Mesure du 14/09 sur la figure REELLEMENT produite, memes donnees
(3 000 frequences annuelles, graine 20260914) :

    avant   axe : 'Prime predite ()'
            quantiles : Q50 = 0 | Q90 = 0 | Q99 = 0
    apres   axe : 'Frequence annuelle predite'
            quantiles : Q50 = 0.1 | Q90 = 0.2 | Q99 = 0.4
    valeurs reelles : 0,1002  0,2343  0,3822

*Le titre disait une grandeur, l'axe en disait une autre, et les valeurs
n'en disaient aucune.* Trois quantiles ecrits << 0 >> sur des frequences
annuelles ne sont pas un arrondi : ils effacent la figure.

⚠️ LA PARENTHESE VIDE EST UNE PROMESSE NON TENUE : `'... ()'` annonce une
unite et n'en donne aucune. L'unite ne s'affiche desormais que si elle
existe.

⚠️⚠️ LES DECIMALES VIENNENT DE LA DONNEE, PAS D'UN LITTERAL, et la regle
a DEUX conditions -- la seconde ajoutee apres mesure :
  1. la plus petite valeur non nulle ne s'ecrit pas << 0 >> ;
  2. deux valeurs DIFFERENTES ne s'ecrivent pas pareil.
Sans la seconde, trois quantiles a 0,101 / 0,102 / 0,103 s'affichaient
<< 0.1 >> trois fois -- ce qui ne dit rien de plus que << 0 >>.
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys
import unittest

import numpy as np

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from core.charts_tarif import (
    _decimales_lisibles,
    chart_distribution_predictions,
)

_A3 = (_RACINE / 'direction_non_vie' / 'tarification' / 'a3_glm'
       / 'agent.py')
_RNG = np.random.default_rng(20260914)
_FREQUENCES = _RNG.gamma(2.0, 0.06, 3000)
_PRIMES = _RNG.gamma(2.0, 420.0, 3000)


def _lire(fig) -> tuple:
    axe = fig.layout.xaxis.title.text or ''
    notes = [a.text for a in (fig.layout.annotations or [])
             if a.text and a.text.startswith('Q')]
    return axe, notes


class TestFigureNommeSaGrandeur(unittest.TestCase):

    # ── FQ-1 ─────────────────────────────────────────────────────────────
    def test_FQ1_l_axe_nomme_la_grandeur_et_jamais_une_autre(self):
        """⚠️ LE TITRE ET L'AXE DOIVENT DIRE LA MEME CHOSE. Un lecteur qui
        les compare ne peut pas trancher lequel ment."""
        axe, _ = _lire(chart_distribution_predictions(
            _FREQUENCES, unite='', grandeur='Fréquence annuelle prédite',
            titre='Distribution des fréquences prédites'))
        self.assertIn(
            'réquence', axe,
            f"l'axe ne nomme pas la grandeur du titre : {axe!r}")
        self.assertNotIn(
            'Prime', axe,
            f"l'axe parle encore de PRIME sous un titre de frequences : "
            f"{axe!r}")
        self.assertNotIn(
            '()', axe,
            f"l'axe porte une parenthese VIDE -- une unite promise et non "
            f"donnee : {axe!r}")
        print(f"    FQ-1 SCEAU : axe = {axe!r}")

    # ── FQ-2 ─────────────────────────────────────────────────────────────
    def test_FQ2_les_quantiles_d_une_frequence_ne_valent_pas_tous_zero(self):
        """⚠️⚠️ TROIS QUANTILES ECRITS « 0 » EFFACENT LA FIGURE. Ce n'est
        pas un arrondi : c'est une autre grandeur."""
        _, notes = _lire(chart_distribution_predictions(
            _FREQUENCES, unite='', grandeur='Fréquence annuelle prédite',
            titre='Distribution des fréquences prédites'))
        self.assertEqual(
            len(notes), 3, f"les trois quantiles ne sont plus annotes : "
                           f"{notes}")
        nuls = [n for n in notes if n.endswith('= 0')]
        self.assertEqual(
            nuls, [],
            f"{len(nuls)} quantile(s) sur {len(notes)} s'ecrivent « 0 » sur "
            f"des frequences annuelles : {notes}")
        self.assertEqual(
            len(set(notes)), len(notes),
            f"deux quantiles portent la MEME etiquette : {notes}")
        print(f"    FQ-2 SCEAU : {notes}")

    # ── FQ-3 ─────────────────────────────────────────────────────────────
    def test_FQ3_l_appel_par_DEFAUT_en_euros_ne_bouge_pas(self):
        """La contre-epreuve : le cas deja correct garde son axe, son unite
        et ses zero decimale."""
        axe, notes = _lire(chart_distribution_predictions(_PRIMES))
        self.assertEqual(
            axe, 'Prime prédite (€)',
            f"l'appel par defaut a change d'axe : {axe!r}")
        self.assertTrue(
            all(n.endswith('€') for n in notes),
            f"l'unite a disparu des quantiles : {notes}")
        self.assertTrue(
            all('.' not in n.split('= ')[1] for n in notes),
            f"des decimales sont apparues sur des primes en euros : {notes}")
        print(f"    FQ-3 SCEAU : {axe!r} / {notes}")

    # ── FQ-4 ─────────────────────────────────────────────────────────────
    def test_FQ4_la_regle_des_decimales_tient_sur_les_cas_SERRES(self):
        """⚠️ LA SECONDE CONDITION A ETE AJOUTEE APRES MESURE, et c'est elle
        qui distingue trois quantiles voisins."""
        cas = {
            (0.101, 0.102, 0.103): 3,
            (0.1002, 0.2343, 0.3822): 1,
            (695.0, 1618.0, 2710.0): 0,
            (0.0, 0.0, 0.0): 0,
            (1.0, 1.0): 0,
        }
        vus = {c: _decimales_lisibles(list(c)) for c in cas}
        self.assertEqual(
            vus, cas,
            f"la regle des decimales a change de comportement : {vus}")
        for valeurs, n in cas.items():
            rendus = [f'{v:.{n}f}' for v in valeurs]
            self.assertEqual(
                len(set(rendus)), len(set(valeurs)),
                f"deux valeurs DIFFERENTES s'ecrivent pareil : {valeurs} -> "
                f"{rendus}")
        print(f"    FQ-4 SCEAU : {len(cas)} cas, regle stable, 0 collision")

    # ── FQ-5 ─────────────────────────────────────────────────────────────
    def test_FQ5_LE_SITE_VIVANT_declare_sa_grandeur(self):
        """⚠️⚠️ LE CORRECTIF NE VAUT QUE SI L'APPELANT DECLARE. Un defaut
        qui reste correct par hasard n'est pas ferme : le releve est par
        AST, sur l'appel reel d'A3."""
        arbre = ast.parse(_A3.read_bytes().decode('utf-8'))
        appels = [n for n in ast.walk(arbre)
                  if isinstance(n, ast.Call)
                  and ast.unparse(n.func).endswith(
                      'chart_distribution_predictions')]
        self.assertEqual(
            len(appels), 1,
            f"A3 ne porte plus un seul appel a cette figure : {len(appels)}")
        mots = {k.arg for k in appels[0].keywords if k.arg}
        self.assertIn(
            'grandeur', mots,
            f"le site vivant ne declare pas `grandeur` : {sorted(mots)}. "
            f"L'axe reprendrait le defaut « Prime predite ».")
        print(f"    FQ-5 SCEAU : l'appel d'A3 declare {sorted(mots)}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
