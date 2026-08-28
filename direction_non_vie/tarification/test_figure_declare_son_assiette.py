"""Controles positifs — lot 4.2 : `charts/C3` et `charts/C5`.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
DEUX CONSTATS, UNE SEULE PROPRIETE : *une figure doit declarer ce qu'elle ne
montre pas.*

`charts/C3` — UNE FIGURE VIDE ETAIT INDISCERNABLE D'UNE FIGURE PLEINE. Les
sept fonctions rendaient un objet COMPLET -- fond navy, titre or, axes titres,
bande verte -- avec ZERO point trace, et aucune ne le disait. Mesure d'origine,
7 cas, `la figure le dit : False` sept fois.

`charts/C5` — TROIS TRONCATURES SILENCIEUSES, mesurees a nouveau le 28/08 :
    relativites   23 fournies -> 15 tracees    la figure le dit : False
    SHAP          30 fournies -> 15 tracees    la figure le dit : False
    walk-forward   4 fenetres ->  2 tracees    la figure le dit : False
                                (quand deux n'ont pas de A/E)

⚠️ ON N'ELARGIT PAS LA TRONCATURE, ON LA DECLARE. Tracer 23 relativites
rendrait la figure illisible : le `top=15` est un choix de lisibilite
defendable. Ce qui ne l'est pas, c'est qu'il soit MUET.

⚠️⚠️ ET LE SOUS-CAS (c) DU RELEVE N'EST PAS REPRODUIT. Il annoncait
<< distribution : 1000 valeurs -> 500 tracees >>. Mesure : **1 000 sur 1 000**,
aucune coupe. *Un sous-cas qui ne se reproduit pas se DECLARE, il ne se corrige
pas* -- et un test ci-dessous fige cette absence de troncature, pour qu'on ne
la reintroduise pas en croyant fermer le constat.

⚠️ ET J'AI MOI-MEME PRODUIT DEUX FAUSSES LECTURES EN TRACANT CE LOT :
`chart_distribution_predictions([])` semblait LEVER, et `chart_lift_decile`
aussi -- c'etait ma sonde (`or` sur un tableau numpy, et un `[]` passe la ou
un `float` etait attendu). *Une sonde qui leve accuse le code a tort aussi
surement qu'une sonde qui ne trouve rien l'absout a tort.*
"""

from __future__ import annotations

import re
import unittest

from core import charts_tarif as CT

_BANDES = {'bande_acceptable': (0.90, 1.10), 'bande_stricte': (0.95, 1.05)}


def _texte(fig) -> str:
    return ' '.join(
        [str(getattr(fig.layout.title, 'text', '') or '')]
        + [str(a.text) for a in (fig.layout.annotations or ())])


#: Les SEPT fonctions, chacune avec une entree VIDE et son mot attendu.
_VIDES = (
    ('chart_residus_qq', lambda: CT.chart_residus_qq([]), 'résidus'),
    ('chart_lift_decile', lambda: CT.chart_lift_decile([]), 'déciles'),
    ('chart_relativites_glm', lambda: CT.chart_relativites_glm({}), 'variables'),
    ('chart_walkforward_ae',
     lambda: CT.chart_walkforward_ae([], **_BANDES), 'fenêtres'),
    ('chart_lorenz_gini', lambda: CT.chart_lorenz_gini([], []), 'points'),
    ('chart_shap_summary', lambda: CT.chart_shap_summary({}), 'variables'),
    ('chart_distribution_predictions',
     lambda: CT.chart_distribution_predictions([]), 'prédictions'),
)


class TestFigureVide(unittest.TestCase):
    """`charts/C3` — une figure sans donnée le dit."""

    def test_les_sept_figures_vides_le_disent(self):
        """⚠️⚠️ LE TEST QUI FERME LE CONSTAT — les sept, pas six."""
        muettes = []
        for nom, fabrique, mot in _VIDES:
            texte = _texte(fabrique())
            if 'AUCUNE DONNÉE' not in texte or mot not in texte:
                muettes.append(nom)
        self.assertEqual(
            muettes, [],
            f"{len(muettes)} figure(s) vide(s) restent muettes : {muettes}")
        print(f"    OK C3-1 les {len(_VIDES)} figures vides déclarent "
              f"« AUCUNE DONNÉE » et NOMMENT ce qui manque")

    def test_le_message_NOMME_ce_qui_manque(self):
        """⚠️ « Aucune donnée » seul ne dit pas de QUOI.

        Sept figures avec le même message ne diraient pas laquelle manque de
        quoi. *C'est le verdict qui agrège contre le motif qui discrimine.*
        """
        mots = {mot for _, _, mot in _VIDES}
        self.assertGreaterEqual(len(mots), 5,
                                'les figures partagent trop de libellés')
        for nom, fabrique, mot in _VIDES:
            with self.subTest(figure=nom):
                self.assertIn(mot, _texte(fabrique()))
        print(f"    OK C3-2 {len(mots)} libellés distincts : le message "
              f"nomme ce qui manque")

    def test_TEMOIN_une_figure_pleine_ne_dit_RIEN(self):
        """⚠️⚠️ SECOND SENS — le filet ne doit pas crier tout le temps.

        Une annotation posée sur toutes les figures ne vaudrait rien : elle
        cesserait d'être un signal.
        """
        for nom, fig in (
                ('lift', CT.chart_lift_decile([1.0, 1.2, 1.5])),
                ('relativités', CT.chart_relativites_glm(
                    {'a': 1.1, 'b': 0.9})),
                ('walk-forward', CT.chart_walkforward_ae(
                    [{'annee': 2020, 'ae_ratio': 1.0}], **_BANDES))):
            with self.subTest(figure=nom):
                texte = _texte(fig)
                self.assertNotIn('AUCUNE DONNÉE', texte)
                self.assertNotRegex(texte, r'\d+ \w+ sur \d+')
        print("    OK C3-3 témoin : une figure pleine ne déclare rien")


class TestTroncatureDeclaree(unittest.TestCase):
    """`charts/C5` — une figure tronquée le dit."""

    def test_les_trois_troncatures_mesurees_sont_declarees(self):
        """⚠️⚠️ LES TROIS MESURES D'ORIGINE, REJOUÉES."""
        cas = (
            ('relativités 23 → 15',
             CT.chart_relativites_glm({f'v{i}': 1.0 + i * 0.05
                                       for i in range(23)}), 15, 23),
            ('SHAP 30 → 15',
             CT.chart_shap_summary({f'f{i}': 1.0 - i * 0.01
                                    for i in range(30)}), 15, 30),
            ('walk-forward 4 → 2',
             CT.chart_walkforward_ae(
                 [{'annee': 2020, 'ae_ratio': 1.0},
                  {'annee': 2021, 'ae_ratio': 1.02},
                  {'annee': 2022, 'ae_ratio': None},
                  {'annee': 2023, 'ae_ratio': None}], **_BANDES), 2, 4),
        )
        for etiquette, fig, traces, fournis in cas:
            with self.subTest(cas=etiquette):
                texte = _texte(fig)
                self.assertRegex(
                    texte, rf'{traces} \w+ sur {fournis}',
                    f'{etiquette} : la troncature reste muette')
                self.assertIn(f'{fournis - traces} autres', texte)
        print("    OK C5-1 23→15 · 30→15 · 4→2 : les trois déclarées, avec "
              "le nombre exact d'absents")

    def test_la_troncature_n_est_pas_ELARGIE(self):
        """⚠️ On DÉCLARE, on n'élargit pas.

        Tracer les 23 relativités rendrait la figure illisible : `top=15` est
        un choix de lisibilité défendable. Fermer le constat en supprimant la
        troncature aurait échangé un défaut contre un autre.
        """
        fig = CT.chart_relativites_glm({f'v{i}': 1.0 + i * 0.05
                                        for i in range(23)})
        n = max(len(getattr(tr, 'y', ()) or ()) for tr in fig.data)
        self.assertEqual(n, 15, 'la troncature a été élargie au lieu d\'être '
                                'déclarée')
        print("    OK C5-2 la troncature reste à 15 : déclarée, pas élargie")

    def test_le_sous_cas_c_du_releve_reste_NON_REPRODUIT(self):
        """⚠️⚠️ LE RELEVÉ DISAIT « distribution : 1000 → 500 ». C'EST FAUX.

        Mesuré : 1 000 sur 1 000, aucune coupe. Ce test FIGE cette absence de
        troncature — pour qu'on ne l'introduise pas en croyant fermer un
        sous-cas qui n'existe pas. *Un sous-cas qui ne se reproduit pas se
        déclare, il ne se corrige pas.*
        """
        fig = CT.chart_distribution_predictions([float(x) for x in range(1000)])
        # ⚠️ `getattr(tr, 'x', ()) or ()` LÈVE sur un tableau numpy non vide
        # (« truth value ... is ambiguous ») — et c'est le piège contre lequel
        # la docstring de ce fichier met en garde. Je viens d'y tomber en
        # l'écrivant. *Une sonde se vérifie comme le code qu'elle mesure.*
        n = max(len(v) for v in
                (getattr(tr, 'x', None) for tr in fig.data) if v is not None)
        self.assertEqual(n, 1000, 'une troncature à 500 est apparue')
        self.assertNotRegex(_texte(fig), r'\d+ \w+ sur \d+')
        print("    OK C5-3 distribution : 1 000 sur 1 000, aucune troncature "
              "— le sous-cas (c) du relevé n'existe pas")

    def test_le_nombre_annonce_EST_le_nombre_trace(self):
        """⚠️ Une déclaration fausse serait pire que le silence.

        On compare le chiffre ÉCRIT à ce qui est réellement dans la figure.
        """
        fig = CT.chart_shap_summary({f'f{i}': 1.0 - i * 0.01
                                     for i in range(30)})
        trace = max(len(getattr(tr, 'y', ()) or ()) for tr in fig.data)
        ecrit = re.search(r'(\d+) \w+ sur (\d+)', _texte(fig))
        self.assertIsNotNone(ecrit, 'rien n\'est déclaré')
        self.assertEqual(int(ecrit.group(1)), trace,
                         'le nombre annoncé n\'est pas le nombre tracé')
        self.assertEqual(int(ecrit.group(2)), 30)
        print(f"    OK C5-4 le nombre annoncé ({ecrit.group(1)}) est bien le "
              f"nombre tracé ({trace})")


if __name__ == '__main__':
    unittest.main()
