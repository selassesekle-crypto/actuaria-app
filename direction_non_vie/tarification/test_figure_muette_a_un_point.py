r"""
==============================================================================
  CE QU'UNE FIGURE DECLARE SE COMPTE SUR CE QU'ELLE DESSINE
==============================================================================

⚠️⚠️ `CHT-1` -- LE QQ-PLOT PUBLIAIT << 1 RESIDUS SUR 2 >> LA OU IL
DESSINAIT ZERO POINT. `chart_residus_qq` passait `traces=int(r.size)` a
`_declarer_assiette` : le nombre de residus FINIS, pas le nombre de
points DESSINES. Or le trace est garde par `if n >= 2:` -- un QQ-plot
n'existe pas a un seul point.

Mesure du 13/09/2026, AVANT le correctif :

    chart_residus_qq([])            0 point   << AUCUNE DONNEE >>      bon
    chart_residus_qq([nan] x 100)   0 point   << AUCUNE DONNEE >>      bon
    chart_residus_qq([0.5])         0 point   AUCUNE PHRASE            <-
    chart_residus_qq([0.5, nan])    0 point   << 1 residus sur 2 >>    <- FAUX
    chart_residus_qq([0.5, 1.2])    2 points  (rien a dire)            bon

*La seconde ligne est la plus grave : une figure qui ne trace rien
publiait une phrase AFFIRMATIVE sur ce qu'elle montrait.* Et le QQ-plot
atteint un document signe : `a3_glm/agent.py` le produit,
`rapport_modeles_tarif.py` le publie.

⚠️⚠️ LE DEFAUT ETAIT ISOLE, ET C'EST MESURE. Releve par AST sur le GESTE
(un `if` comparant une taille a un entier et enveloppant un `add_trace`)
et non sur le texte : **`n >= 2` est le SEUL garde de ce genre dans tout
le module**. Les six autres figures dessinent bien leur point unique --
lift 1, Lorenz 2, relativites 1, SHAP 1, distribution 1 -- et le
walk-forward, qui n'en dessine aucun, se DECLARE vide. *Une seule
fonction pouvait dessiner zero point en se taisant.*

⚠️⚠️ ET UN CONTROLE DU DEPOT ATTESTAIT LE DEFAUT COMME ACCEPTABLE.
`test_residus_insuffisants` appelait exactement `chart_residus_qq([0.3])`,
commentait << n<2 -> figure themee sans points >> et n'affirmait que
`isinstance(fig, go.Figure)`. *Un controle qui NOMME le defaut et le
benit est pire qu'un controle absent : il rassure.* Il a ete relu dans le
meme lot.

⚠️ CE QUE CE FICHIER SURVEILLE EN PLUS DE L'OCCURRENCE : la CLASSE.
`test_figure_declare_son_assiette` couvre les sept figures, mais chacune
avec une ENTREE VIDE -- son assiette est << entree vide >>, jamais
<< rien de dessine >>. `QQ-3` ci-dessous ajoute l'assiette manquante :
**une seule valeur**, sur les sept.
==============================================================================
"""
from __future__ import annotations

import math
import os
import pathlib
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from core import charts_tarif as ct

_NAN = float('nan')


def _points(fig) -> int:
    """Le nombre de points REELLEMENT poses sur la figure.

    ⚠️ `trace.x` est un ndarray : `or ()` le ferait passer par son test de
    verite et leverait << truth value is ambiguous >> des qu'il porte plus
    d'un point. On teste `is not None`, jamais la verite."""
    n = 0
    for tr in fig.data:
        for axe in ('x', 'values', 'labels'):
            v = getattr(tr, axe, None)
            if v is not None:
                n = max(n, len(v))
    return n


def _declare(fig) -> str:
    return ' | '.join((a.text or '') for a in (fig.layout.annotations or ()))


#: ⚠️ LES SEPT FIGURES AVEC **UNE SEULE** VALEUR -- l'assiette que le
#: garde-fou voisin n'a pas : lui n'essaie que l'entree VIDE.
_UN_POINT = (
    ('chart_lift_decile', lambda: ct.chart_lift_decile([0.12])),
    ('chart_lorenz_gini', lambda: ct.chart_lorenz_gini([0.5], [0.5])),
    ('chart_relativites_glm',
     lambda: ct.chart_relativites_glm({'age': 1.2})),
    ('chart_walkforward_ae',
     lambda: ct.chart_walkforward_ae(
         [{'annee': 2024, 'ae_ratio': 1.02}],
         bande_acceptable=(0.90, 1.10), bande_stricte=(0.95, 1.05))),
    ('chart_shap_summary', lambda: ct.chart_shap_summary({'age': 0.3})),
    ('chart_distribution_predictions',
     lambda: ct.chart_distribution_predictions([0.5])),
    ('chart_residus_qq', lambda: ct.chart_residus_qq([0.5])),
)


class TestUneFigureMuetteAUnPoint(unittest.TestCase):

    def test_QQ1_SCEAU_un_seul_residu_fait_DIRE_pourquoi_c_est_vide(self):
        """⚠️⚠️ LE SCEAU. Avec UN residu fini le QQ-plot ne trace rien : il
        doit le DIRE, et dire POURQUOI. *<< aucune donnee >> tout court
        ferait croire a un portefeuille vide alors qu'un residu EXISTE ; le
        lecteur doit pouvoir distinguer << rien a tracer >> de << pas assez
        pour ce graphique >>.*"""
        fig = ct.chart_residus_qq([0.5])
        self.assertEqual(_points(fig), 0,
                         'un QQ-plot a un seul point ne devrait rien tracer')
        texte = _declare(fig)
        self.assertTrue(texte,
                        'la figure ne trace RIEN et ne dit RIEN : elle est '
                        'visuellement indiscernable d une figure pleine')
        for attendu in ('au moins 2 points', '1 disponible'):
            self.assertIn(
                attendu, texte,
                f"la figure ne nomme pas {attendu!r} : {texte!r}")
        print(f"    QQ-1 SCEAU : 1 residu -> 0 point, declare "
              f"{len(texte)} caracteres")

    def test_QQ2_SCEAU_la_phrase_de_TRONCATURE_ne_ment_plus(self):
        """⚠️⚠️ LE CAS LE PLUS GRAVE, ET IL EST DIFFERENT DU PREMIER. Avec
        `[0.5, nan]` la figure publiait << 1 residus sur 2 >> : une phrase
        AFFIRMATIVE decrivant ce qu'elle montrait, sur une figure qui ne
        montrait rien. Une absence est un trou ; une affirmation fausse est
        une erreur DANS le document signe."""
        fig = ct.chart_residus_qq([0.5, _NAN])
        self.assertEqual(_points(fig), 0)
        texte = _declare(fig)
        self.assertNotIn(
            'sur 2', texte,
            f"la figure publie encore une phrase de TRONCATURE alors qu'elle "
            f"ne trace aucun point : {texte!r}")
        self.assertIn('au moins 2 points', texte,
                      f'la figure ne dit pas le vrai motif : {texte!r}')
        print("    QQ-2 SCEAU : [0.5, nan] -> 0 point, aucune phrase de "
              "troncature")

    def test_QQ3_SCEAU_aucune_des_SEPT_ne_dessine_RIEN_en_silence(self):
        """⚠️⚠️ LE SCEAU DE LA CLASSE, PAS DE L'OCCURRENCE. Le garde-fou
        voisin essaie les sept figures avec une entree VIDE ; son assiette
        est << entree vide >>, jamais << rien de dessine >>. On ajoute ici
        l'assiette qui manquait : **une seule valeur**. Toute figure qui
        pose zero point doit le declarer, quelle qu'en soit la cause."""
        muettes = []
        for nom, fabrique in _UN_POINT:
            fig = fabrique()
            n, texte = _points(fig), _declare(fig)
            if n == 0 and not texte:
                muettes.append(nom)
        self.assertEqual(
            muettes, [],
            f"{len(muettes)} figure(s) sur {len(_UN_POINT)} dessinent ZERO "
            f"point sur une entree a UNE valeur et ne le disent pas : "
            f"{muettes}. *Une figure vide est visuellement indiscernable "
            f"d'une figure pleine.*")
        print(f"    QQ-3 SCEAU : 0 / {len(_UN_POINT)} figure(s) muette(s) a "
              f"une seule valeur")

    def test_QQ4_CONTRE_EPREUVE_deux_residus_tracent_et_se_taisent(self):
        """⚠️ LE SECOND SENS. Un correctif qui ferait parler la figure a tous
        les coups poserait un avertissement permanent, donc un avertissement
        qu'on cesse de lire."""
        for residus, attendu in (([0.5, 1.2], 2), ([0.5, 1.2, -0.3], 3),
                                 (list(range(2000)), 2000)):
            fig = ct.chart_residus_qq(residus)
            self.assertEqual(_points(fig), attendu,
                             f'{len(residus)} residus -> {_points(fig)} '
                             f'point(s), attendu {attendu}')
            self.assertEqual(
                _declare(fig), '',
                f'la figure parle alors qu elle trace tout : '
                f'{_declare(fig)!r}')
        #: ⚠️ ET LES DEUX CAS DEJA JUSTES NE BOUGENT PAS : une entree vide
        #: ou entierement non finie garde son annonce d'origine.
        for residus in ([], [_NAN] * 100, [_NAN]):
            fig = ct.chart_residus_qq(residus)
            self.assertEqual(_points(fig), 0)
            self.assertIn('AUCUNE DONN', _declare(fig))
            self.assertNotIn('au moins 2 points', _declare(fig),
                             'un portefeuille VIDE recoit le motif du seuil : '
                             'les deux causes ne sont plus distinguables')
        print('    QQ-4 contre-epreuve : 2/3/2000 residus traces et muets ; '
              'vide et NaN gardent << AUCUNE DONNEE >> seul')

    def test_QQ5_CONTRE_EPREUVE_les_TRONCATURES_voisines_parlent_encore(self):
        """⚠️⚠️ CE QUE CE LOT NE DOIT SURTOUT PAS DEPLACER. `_declarer_
        assiette` est partagee par les sept figures : un correctif pose LA
        aurait casse les troncatures legitimes. Il a ete pose dans
        `chart_residus_qq` SEULE -- et on le verifie sur les voisines."""
        rel = {f'v{i}': 1.0 + i / 100 for i in range(23)}
        texte = _declare(ct.chart_relativites_glm(rel))
        self.assertIn('sur 23', texte,
                      f'la troncature des relativites ne se dit plus : '
                      f'{texte!r}')
        pred = [0.5] * 500 + [_NAN] * 500
        texte2 = _declare(ct.chart_distribution_predictions(pred))
        #: ⚠️ ON CHERCHE DANS LE TEXTE TEL QU'IL EST. Ma premiere
        #: redaction retirait les espaces AVANT de chercher `'sur 1000'`
        #: -- qui en contient un : le controle rougissait sur une phrase
        #: pourtant juste. *Un controle trop etroit ACCUSE, et la
        #: NORMALISATION qu'il applique avant de comparer en fait partie.*
        self.assertIn(
            'sur 1000', texte2,
            f'la troncature de la distribution ne se dit plus : {texte2!r}')
        print('    QQ-5 contre-epreuve : relativites 15/23 et distribution '
              '500/1000 declarent toujours leur troncature')

    def test_QQ6_le_compteur_passe_a_la_declaration_est_celui_du_DESSIN(self):
        """⚠️ LA PROPRIETE, MESUREE PLUTOT QUE LUE. Sur toute entree, le
        nombre annonce comme trace doit egaler le nombre de points poses.
        *C'est l'invariant que `CHT-1` violait, et il se verifie sans
        regarder le code.*"""
        nan = _NAN
        cas = [[], [nan], [nan] * 7, [0.5], [0.5, nan], [0.5, 1.2],
               [0.5, 1.2, nan], list(range(50))]
        for residus in cas:
            fig = ct.chart_residus_qq(residus)
            n = _points(fig)
            texte = _declare(fig)
            finis = sum(1 for v in residus
                        if isinstance(v, (int, float)) and math.isfinite(v))
            if n == 0:
                self.assertTrue(
                    texte,
                    f'{len(residus)} valeur(s) dont {finis} finie(s) : 0 '
                    f'point trace et AUCUNE declaration')
                self.assertNotIn(
                    f'{finis} r', texte,
                    f'la figure annonce {finis} residus traces alors qu elle '
                    f'en trace 0 : {texte!r}')
        print(f"    QQ-6 : {len(cas)} entrees, aucune n annonce plus de "
              f"points qu elle n en dessine")


if __name__ == '__main__':
    unittest.main(verbosity=2)
