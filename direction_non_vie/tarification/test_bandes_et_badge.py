"""Controles positifs — lot 4.1 : `charts/C1` et `charts/C2`.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
`charts/C1` — LE BADGE N'AVAIT AUCUNE BORNE. Il ecrivait `100 * mod / obs`
sous le seul garde `obs > 0`. Mesure d'origine :

    obs=0,8320  mod=0,1780  ->  << soit 21 % du discriminable >>      (juste)
    obs=0,2000  mod=0,2500  ->  << soit 125 % du discriminable >>
    obs=0,2000  mod=-0,0105 ->  << soit -5 % du discriminable >>
    obs=1e-6    mod=0,1800  ->  << soit 18 000 000 % du discriminable >>

⚠️⚠️ ON N'ECRETE PAS A [0, 100], ET C'EST LA LECON DU LOT F1 D'A7 : juger une
valeur ecretee est une tautologie, et l'ecretement CACHE la divergence au lieu
de la dire. Le 125 % n'est pas une aberration de calcul -- la docstring
l'explique : le plafond est calcule sur le portefeuille ENTIER, le Gini du
modele sur la seule base de TEST. *Deux assiettes.*

⚠️ UNE SEULE CONDITION COUVRE LES TROIS CAS, SANS INVENTER DE SEUIL : le
rapport n'est une PART que si `0 <= mod <= obs`. Un seuil fabrique ici aurait
ete le defaut meme que cet audit poursuit.

`charts/C2` — TROIS BANDES COEXISTAIENT, et la plus visible etait la plus
large :

    rectangle vert de la figure       0,85 - 1,15   <- le plus LARGE
    point VERT de la meme figure      0,95 - 1,05
    le verrou qui plafonne le statut  0,90 - 1,10   <- la DECISION

Un A/E de 0,87 se dessinait DANS la bande verte, et le verrou avertissait.

⚠️ LE REMEDE N'EST PAS DE RECOPIER LE BON NOMBRE : la figure ne possede plus
AUCUN seuil, elle RECOIT les deux bandes de qui decide.

⚠️⚠️ ET IL Y A UN HOMONYME QUI N'A PAS ETE FUSIONNE. L'analyse PAR SEGMENT
d'A6 gradue elle aussi sur `0,90 - 1,10` -- mais la, c'est le VERT (<< non
biaise sur ce segment >>), avec un AMBRE a 0,80 - 1,20. Sur une FENETRE,
`0,90 - 1,10` est l'AMBRE. *Deux echelles, deux objets, les memes nombres.*
Un test ci-dessous FIGE cette distinction.
"""

from __future__ import annotations

import re
import unicodedata
import unittest

from core.charts_tarif import chart_lorenz_gini, chart_walkforward_ae
from core.conformite_reglementaire import (
    AE_FENETRE_ACCEPTABLE,
    AE_FENETRE_STRICTE,
)

#: Une courbe de Lorenz quelconque — ce lot ne teste pas la courbe, il teste
#: ce que le badge ECRIT a cote.
_XS = [i / 20 for i in range(21)]
_YS = [x ** 0.7 for x in _XS]


def _badge(obs: float, mod: float) -> str:
    fig = chart_lorenz_gini(_XS, _YS, obs, gini_modele=mod)
    return ' '.join(str(a.text) for a in (fig.layout.annotations or ()))


class TestBadgeDiscriminable(unittest.TestCase):
    """`charts/C1` — le badge ne publie une part que si c'en est une."""

    def test_le_cas_nominal_publie_toujours_sa_part(self):
        """⚠️ SECOND SENS D'ABORD — corriger ne doit pas éteindre le badge.

        Un correctif qui cesserait de publier la part fermerait le constat en
        détruisant l'information que la figure porte.
        """
        self.assertRegex(_badge(0.8320, 0.1780), r'soit\s+21\s*%')
        print("    OK C1-1 cas nominal : « soit 21 % du discriminable » publié")

    def test_les_trois_cas_pathologiques_ne_publient_plus_de_part(self):
        """⚠️⚠️ LES TROIS MESURES D'ORIGINE, REJOUÉES."""
        for etiquette, obs, mod in (('modèle > plafond', 0.2000, 0.2500),
                                    ('modèle NÉGATIF', 0.2000, -0.0105),
                                    ('plafond ~ nul', 1e-6, 0.1800)):
            with self.subTest(cas=etiquette):
                texte = _badge(obs, mod)
                self.assertNotRegex(
                    texte, r'soit\s+-?\d+\s*%',
                    f'{etiquette} : une part est encore publiée')
                self.assertIn('non publiée', texte,
                              f'{etiquette} : le badge se tait sans le dire')
        print("    OK C1-2 125 % · -5 % · 18 000 000 % : plus aucune part "
              "publiée, et chacune dit pourquoi")

    def test_le_motif_NOMME_la_cause(self):
        """⚠️ Se taire ne suffit pas : le lecteur doit savoir POURQUOI.

        ⚠️⚠️ ET LES TROIS CAS DU RELEVÉ DONNENT **DEUX** MOTIFS, PAS TROIS —
        c'est une décision, pas un oubli, et ce test la FIGE pour qu'on ne la
        « corrige » pas par accident.

        `obs = 1e-6, mod = 0,18` tombe dans « le modèle dépasse le plafond »,
        et c'est EXACT : `0,18 > 1e-6`. Distinguer « le plafond est
        dégénéré » de « le modèle dépasse le plafond » exigerait un SEUIL sur
        ce qu'est un plafond trop petit — *un seuil fabriqué serait le défaut
        même que cet audit poursuit*. Le motif publié reste vrai dans les deux
        cas ; il est simplement moins précis dans l'un des deux, et on le dit
        ici plutôt que d'inventer un nombre.

        ⚠️ La branche `obs <= 0` n'est pas morte pour autant : elle sert quand
        le plafond est nul ou NÉGATIF (`obs = -0,1, mod = 0,2`), où « dépasse
        le plafond » induirait en erreur.
        """
        motifs = {etq: _badge(o, m).split('non publiée')[1]
                  for etq, o, m in (('sup', 0.2, 0.25), ('neg', 0.2, -0.0105),
                                    ('nul', 1e-6, 0.18), ('negatif', -0.1, 0.2))}
        self.assertIn("l'envers", motifs['neg'])
        self.assertIn('assiette', motifs['sup'])
        self.assertEqual(motifs['nul'], motifs['sup'],
                         "le cas du plafond minuscule doit partager le motif "
                         "de « dépasse le plafond » — sinon un seuil a été "
                         "inventé")
        self.assertIn('aucun plafond', motifs['negatif'])
        self.assertEqual(len(set(motifs.values())), 3,
                         'les motifs ne discriminent plus les trois causes')
        print("    OK C1-3 trois causes distinctes, et le plafond minuscule "
              "partage DÉLIBÉRÉMENT le motif du dépassement")

    def test_aucun_ecretement_a_100(self):
        """⚠️⚠️ La leçon F1 d'A7 : écrêter CACHE la divergence.

        Le badge ne doit nulle part borner la valeur à 100 — il refuse de la
        publier, ce qui n'est pas la même chose.
        """
        import inspect

        from core import charts_tarif as CT
        src = unicodedata.normalize(
            'NFC', inspect.getsource(CT.chart_lorenz_gini))
        for forme in (r'min\s*\(\s*100', r'max\s*\(\s*0', r'clip\s*\('):
            self.assertNotRegex(
                src, forme,
                f'un écrêtement ({forme}) est apparu : la divergence serait '
                f'cachée au lieu d\'être dite')
        print("    OK C1-4 aucun écrêtement : le badge se tait, il ne borne pas")


class TestBandesWalkForward(unittest.TestCase):
    """`charts/C2` — la figure dessine la bande de la RÈGLE."""

    def _figure(self, ae):
        return chart_walkforward_ae(
            [{'annee': 2020 + i, 'ae_ratio': v} for i, v in enumerate(ae)],
            bande_acceptable=AE_FENETRE_ACCEPTABLE,
            bande_stricte=AE_FENETRE_STRICTE)

    def test_le_rectangle_dessine_EST_la_bande_qui_decide(self):
        """⚠️⚠️ LE TEST QUI FERME LE CONSTAT."""
        fig = self._figure([1.0])
        rects = [(round(float(s.y0), 6), round(float(s.y1), 6))
                 for s in (fig.layout.shapes or ())
                 if getattr(s, 'type', '') == 'rect']
        self.assertEqual(
            rects, [(AE_FENETRE_ACCEPTABLE[0], AE_FENETRE_ACCEPTABLE[1])],
            'le rectangle dessiné n\'est pas la bande de la règle')
        print(f"    OK C2-1 rectangle dessiné = {rects[0]} = la bande de la règle")

    def test_le_cas_mesure_du_releve_087(self):
        """⚠️ LA MESURE D'ORIGINE : A/E = 0,87 était DANS la bande verte
        dessinée, et le verrou avertissait."""
        fig = self._figure([0.87])
        couleurs = [tr.marker.color for tr in fig.data
                    if getattr(tr, 'marker', None) is not None
                    and getattr(tr.marker, 'color', None)]
        self.assertTrue(couleurs, 'aucun point tracé')
        self.assertNotIn(
            'rgba(0,229,160', str(couleurs[0][0]),
            '0,87 est encore peint comme acceptable')
        self.assertLess(0.87, AE_FENETRE_ACCEPTABLE[0],
                        '0,87 devrait être HORS de la bande de la règle')
        print("    OK C2-2 A/E = 0,87 : hors bande dessinée ET hors décision")

    def test_la_figure_ne_possede_AUCUN_seuil(self):
        """⚠️ Contrôle par lecture de source — la propriété, pas la valeur.

        Recopier le bon nombre aurait fermé le constat pour un temps ; ce test
        interdit qu'un seuil réapparaisse dans la figure.
        """
        import inspect

        from core import charts_tarif as CT
        src = unicodedata.normalize(
            'NFC', inspect.getsource(CT.chart_walkforward_ae))
        corps = src.split('"""')[2] if src.count('"""') >= 2 else src
        # ⚠️ ON RETIRE LES `rgba(...)` AVANT DE CHERCHER, et c'est un piège
        # que ce test m'a tendu à moi-même : le canal ALPHA d'une couleur
        # (`rgba(240,85,35,0.95)`) a exactement la forme d'un seuil.
        # *Un relevé par symbole ne voit pas l'homonyme.*
        corps = re.sub(r'rgba?\([^)]*\)', '', corps)
        fautifs = re.findall(r'(?<![\d.])(0\.8\d|0\.9\d|1\.0\d|1\.1\d)(?![\d])',
                             corps)
        self.assertEqual(
            fautifs, [],
            f'des seuils littéraux sont revenus dans la figure : {fautifs}')
        print("    OK C2-3 la figure ne porte aucun seuil littéral")

    def test_les_deux_bandes_sont_REQUISES(self):
        """⚠️⚠️ SECOND SENS — un défaut laisserait dessiner une bande périmée.

        *« Présent mais VIDE » a déjà mordu trois fois dans cet audit.*
        """
        with self.assertRaises(TypeError):
            chart_walkforward_ae([{'annee': 2020, 'ae_ratio': 1.0}])
        print("    OK C2-4 omettre une bande LÈVE : aucune bande implicite")

    def test_l_echelle_par_SEGMENT_n_a_PAS_ete_fusionnee(self):
        """⚠️⚠️ L'HOMONYME, FIGÉ.

        A6 gradue le A/E PAR SEGMENT sur `0,90–1,10` = VERT, avec un AMBRE à
        `0,80–1,20`. Sur une FENÊTRE, `0,90–1,10` est l'AMBRE. Les mêmes
        nombres, deux objets. Unifier les six sites sous une constante aurait
        mélangé les deux — ce test l'interdit.
        """
        import inspect

        from direction_non_vie.tarification.a6_comparaison import agent as A6
        src = unicodedata.normalize('NFC', inspect.getsource(A6))
        self.assertIn(
            "'VERT'  if 0.90 <= r <= 1.10 else", src,
            "l'échelle par SEGMENT a été fusionnée avec celle des fenêtres")
        self.assertIn("'AMBRE' if 0.80 <= r <= 1.20 else 'ROUGE')", src)
        print("    OK C2-5 l'échelle par SEGMENT reste distincte — homonyme "
              "préservé")

    def test_le_libelle_publie_lit_la_meme_bande(self):
        """⚠️ Le texte de recommandation citait `[0.90, 1.10]` en dur.

        Un libellé recopié devient faux au premier ajustement, sans que rien
        ne tombe — même geste que `SEUIL_CV_INSTABLE`.
        """
        import inspect

        from direction_non_vie.tarification.a6_comparaison import agent as A6
        src = unicodedata.normalize('NFC', inspect.getsource(A6))
        self.assertIn('AE_FENETRE_ACCEPTABLE[0]:.2f', src,
                      'le libellé de recommandation ne lit plus la bande')
        self.assertNotIn('sort de [0.90, 1.10]', src)
        print("    OK C2-6 le libellé publié dérive de la bande, il ne la "
              "recopie plus")


if __name__ == '__main__':
    unittest.main()
