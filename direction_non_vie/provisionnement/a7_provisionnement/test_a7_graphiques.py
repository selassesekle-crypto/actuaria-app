# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 Ibrahim — le filet des 14 graphiques (lot C2)
=============================================================================

 ⚠️ POURQUOI CE FICHIER EXISTE.

 Les 14 graphiques d'A7 n'étaient épinglés par RIEN. Aucun test ne vérifiait
 qu'une courbe trace bien la grandeur que son étiquette annonce. Un graphique
 faux ne casse aucun test : il s'affiche, il est beau, et il ment.

 L'audit du lot C2 a recalculé chaque série INDÉPENDAMMENT depuis `C`, `n2`,
 `n3`, `n4`, puis l'a comparée à ce qui est réellement tracé. Ce fichier fige
 ce travail pour qu'il ne se reperde jamais : chaque verrou ci-dessous
 RECALCULE la série attendue depuis la source, il ne relit pas la figure.

 CE FILET N'EST PAS UN CONSTAT DE CONFORMITÉ GÉNÉRALE. L'audit a trouvé trois
 défauts, et ils sont ici aussi — écrits comme des assertions de ce qui DEVRAIT
 être vrai, marquées `@unittest.expectedFailure`. Le marqueur se démonte tout
 seul : le jour où le lot C3 corrige le défaut, le test réussit alors qu'on
 attendait un échec, et unittest fait ÉCHOUER la campagne (vérifié :
 `wasSuccessful()` rend False sur un `unexpectedSuccess`). Impossible de
 corriger le code et d'oublier le marqueur.
=============================================================================
"""

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS)

#: Le catalogue, dans l'ordre de `generer_graphiques`.
CATALOGUE = (
    'g1_heatmap', 'g2_cadences', 'g3_facteurs_cl', 'g4_ibnr',
    'g5_convergence', 'g6_bootstrap', 'g7_scr', 'g8_h1', 'g9_h2',
    'g10_h3', 'g11_ultimates', 'g12_sensibilites', 'g13_paiements',
    'g14_backtesting',
)

_CACHE = {}


def _run(avec_primes):
    """Un run complet, mis en cache — l'agent est cher, on ne le lance que 2×."""
    if avec_primes in _CACHE:
        return _CACHE[avec_primes]
    C = np.asarray(GENINS, dtype=float)
    kw = {}
    if avec_primes:
        kw['primes'] = np.full(C.shape[0], float(np.nanmean(C[:, 0])) * 8.0)
    _CACHE[avec_primes] = AgentA7Provisionnement(verbose=False).run(
        source=C, mode_declare='cumule', generer_graphiques=True,
        generer_word=False, n_sim_bootstrap=60, seed=42, **kw)
    return _CACHE[avec_primes]


def _figures(avec_primes=True):
    r = _run(avec_primes)
    g = r.get('graphiques') or {}
    if not g:
        raise unittest.SkipTest('plotly absent — aucun graphique produit')
    return g, np.asarray(GENINS, dtype=float), r['n2'], r['n3'], r['n4']


def _tr(fig, nom):
    """La trace nommée `nom` — exacte d'abord, sinon par préfixe.

    Le préfixe est nécessaire parce que g5 suffixe ses noms du poids retenu
    (« Chain Ladder (53%) ») ; l'exact passe en premier pour que « 1 » ne
    puisse pas attraper « 10 ».
    """
    for t in fig.data:
        if str(t.name or '') == nom:
            return t
    for t in fig.data:
        if str(t.name or '').startswith(nom):
            return t
    raise AssertionError(
        'trace %r absente ; présentes : %s'
        % (nom, [str(t.name) for t in fig.data]))


def _f(seq):
    """Une suite de flottants. `is None` et non `or ()` : un tableau numpy
    vide ou à plusieurs éléments n'a pas de valeur de vérité."""
    return [] if seq is None else [float(v) for v in seq]


# =============================================================================
#  T1 — LE CATALOGUE EST CLOS
# =============================================================================

class T1_Le_Catalogue_Est_Clos(unittest.TestCase):
    """Un 15ᵉ graphique ne peut pas apparaître sans passer par ce fichier."""

    def test_les_quatorze_sont_produits_et_seulement_eux(self):
        g, *_ = _figures()
        self.assertEqual(
            tuple(sorted(g)), tuple(sorted(CATALOGUE)),
            'catalogue modifié — épingle le nouveau graphique à sa source '
            'avant de l\'ajouter')
        print('    OK C2-0 les 14 graphiques, et seulement eux')

    def test_g10_est_le_seul_a_pouvoir_manquer_et_c_est_correct(self):
        """⚠️ LE BON COMPORTEMENT FACE À UNE MÉTHODE INDISPONIBLE.

        Sans primes, Bornhuetter-Ferguson n'existe pas. `g10_h3`, qui trace
        son loss ratio, ne se rabat PAS sur zéro : il ne se produit pas du
        tout, et l'orchestrateur le journalise en « pas de données ».
        C'est le contre-exemple exact de g5 et g11 (voir T3) — la bonne
        réponse existe déjà dans le même fichier.
        """
        g, _, _, n3, _ = _figures(avec_primes=False)
        self.assertFalse(n3['bf']['disponible'])
        self.assertEqual(sorted(set(CATALOGUE) - set(g)), ['g10_h3'],
                         'la liste des graphiques absents sans exposition a '
                         'changé')
        print('    OK C2-0b sans exposition : 13/14, g10 s\'efface au lieu de '
              'tracer zéro')


# =============================================================================
#  T2 — CHAQUE GRAPHIQUE EST ÉPINGLÉ À SA SOURCE
# =============================================================================

class T2_Chaque_Graphique_Est_Epingle(unittest.TestCase):

    def test_g1_la_heatmap_est_le_triangle(self):
        g, C, _, _, _ = _figures()
        z = np.asarray(g['g1_heatmap'].data[0].z, dtype=float)
        self.assertEqual(z.shape, C.shape)
        n, m = C.shape
        connu = np.zeros(C.shape, dtype=bool)
        for i in range(n):
            connu[i, :min(n - i - 1, m - 1) + 1] = True
        np.testing.assert_allclose(z[connu], C[connu], rtol=1e-9)
        self.assertTrue(
            np.isnan(z[~connu]).all(),
            'une case FUTURE porte une valeur : le triangle brut la stocke à '
            'zéro, la heatmap doit la masquer et non peindre « 0 € payé »')
        print('    OK C2-1 g1 : %d cases connues == le triangle, %d cases '
              'futures masquées' % (int(connu.sum()), int((~connu).sum())))

    def test_g2_les_cadences_sont_la_fraction_developpee(self):
        g, C, _, n3, _ = _figures()
        pct = _f(n3['chain_ladder']['pct_developpe'])
        n, m = C.shape
        verifiees = 0
        for i in range(n):
            k = min(n - i - 1, m - 1)
            if C[i, k] <= 0:
                continue
            att = [round(C[i, j] / C[i, k] * pct[i], 4)
                   for j in range(k + 1) if C[i, j] > 0]
            obs = _f(_tr(g['g2_cadences'], 'An. %d' % i).y)
            self.assertEqual([round(v, 4) for v in obs], att,
                             'année %d : la courbe n\'est pas C[i,j]/C[i,k] '
                             '× pct_developpe[i]' % i)
            verifiees += 1
        self.assertGreaterEqual(verifiees, 9)
        y = _f(_tr(g['g2_cadences'], 'An. 0').y)
        self.assertLessEqual(max(y), 1.0001,
                             'une fraction développée dépasse 100 %')
        print('    OK C2-2 g2 : %d courbes == C[i,j]/C[i,k] × pct_developpe[i]'
              % verifiees)

    def test_g3_les_barres_sont_les_facteurs_chain_ladder(self):
        g, _, _, n3, _ = _figures()
        att = _f(n3['chain_ladder']['facteurs'])
        obs = _f(_tr(g['g3_facteurs_cl'], 'Facteurs CL').y)
        np.testing.assert_allclose(obs, att, rtol=1e-9)
        print('    OK C2-3 g3 : %d barres == n3.chain_ladder.facteurs'
              % len(att))

    def test_g4_l_ibnr_et_son_cumul(self):
        g, _, _, n3, _ = _figures()
        att = _f(n3['chain_ladder']['ibnr_par_annee'])
        obs = _f(_tr(g['g4_ibnr'], 'IBNR par année').y)
        np.testing.assert_allclose(obs, att, rtol=1e-9)
        cum = _f(_tr(g['g4_ibnr'], 'IBNR cumulé').y)
        np.testing.assert_allclose(cum, np.cumsum(att), rtol=1e-9)
        self.assertAlmostEqual(cum[-1], sum(att), places=2)
        print('    OK C2-4 g4 : barres == ibnr_par_annee, courbe == leur cumul')

    def test_g5_chaque_barre_est_la_reserve_de_sa_methode(self):
        g, _, _, n3, n4 = _figures()
        att = {
            'Chain Ladder':         n3['chain_ladder']['reserve_totale'],
            'Bornhuetter-Ferguson': n3['bf']['reserve_totale'],
            'Cape Cod':             n3['cape_cod']['reserve_totale'],
            'BE S2':                n4['best_estimate'],
        }
        for lbl, v in att.items():
            obs = _f(_tr(g['g5_convergence'], lbl).y)
            self.assertAlmostEqual(obs[0], float(v), places=2,
                                   msg='barre %r' % lbl)
        be = float(n4['best_estimate'])
        bornes = [float(att['Bornhuetter-Ferguson']),
                  float(att['Chain Ladder'])]
        self.assertTrue(min(bornes) <= be <= max(bornes),
                        'le BE tracé sort de l\'enveloppe des méthodes')
        print('    OK C2-5 g5 : 4 barres == les réserves publiées, BE dans '
              'l\'enveloppe')

    def test_g6_l_histogramme_est_la_distribution_bootstrap(self):
        g, _, _, n3, _ = _figures()
        att = _f((n3.get('bootstrap') or {}).get('distribution'))
        obs = _f(g['g6_bootstrap'].data[0].x)
        self.assertEqual(len(obs), len(att))
        np.testing.assert_allclose(sorted(obs), sorted(att), rtol=1e-9)
        print('    OK C2-6 g6 : %d tirages == bootstrap.distribution'
              % len(att))

    def test_g7_les_segments_sont_l_echelle_des_percentiles(self):
        """Le SUBSTRAT du donut est juste — c'est son étiquette qui ment.

        Voir `T3.test_g7_le_quatrieme_segment_devrait_etre_le_scr`.
        """
        g, _, _, _, n4 = _figures()
        be = float(n4['best_estimate'])
        p75 = float(n4.get('reserve_p75', be))
        p90 = float(n4['reserve_p90'])
        p995 = float(n4['reserve_p99_5'])
        obs = _f(g['g7_scr'].data[0].values)
        np.testing.assert_allclose(
            obs, [be, p75 - be, p90 - p75, p995 - p90], rtol=1e-9)
        self.assertAlmostEqual(sum(obs), p995, places=2,
                               msg='le donut ne totalise plus le P99.5 — un '
                                   'segment a été écrêté à 0 en silence')
        print('    OK C2-7 g7 : les 4 segments == les incréments BE→P75→P90→'
              'P99.5, total == P99.5')

    def test_g8_les_barres_sont_les_correlations_de_h1(self):
        g, _, n2, _, _ = _figures()
        det = (n2.get('h1_independance') or {}).get('details') or []
        att = [abs(float(d.get('corr', 0))) for d in det]
        obs = _f(_tr(g['g8_h1'], '').y) if not att else _f(g['g8_h1'].data[0].y)
        np.testing.assert_allclose(obs, att, rtol=1e-9)
        self.assertTrue(all(v >= 0 for v in obs),
                        'une corrélation est tracée signée alors que l\'axe '
                        'annonce une valeur absolue')
        print('    OK C2-8 g8 : %d barres == |corr| des colonnes de CLM-H1'
              % len(att))

    def test_g9_la_heatmap_est_l_ecart_au_facteur_agrege(self):
        g, C, _, n3, _ = _figures()
        f_cl = _f(n3['chain_ladder']['facteurs'])
        z = np.asarray(g['g9_h2'].data[0].z, dtype=float)
        n, m = C.shape
        compares = 0
        for i in range(n):
            for j in range(min(n - i - 1, len(f_cl))):
                if not (C[i, j] > 0 and f_cl[j]):
                    continue
                att = (C[i, j + 1] / C[i, j] / f_cl[j] - 1.0) * 100.0
                self.assertLess(
                    abs(float(z[i][j]) - att), 0.051,
                    'case (%d,%d) : %s tracé, %.2f attendu'
                    % (i, j, z[i][j], att))
                compares += 1
        self.assertGreaterEqual(compares, 40)
        print('    OK C2-9 g9 : %d cases == (f_individuel / f_CL − 1) × 100'
              % compares)

    def test_g10_la_ligne_de_reference_est_le_lr_a_priori(self):
        g, _, _, n3, _ = _figures()
        lr = float(n3['bf']['lr_apriori'])
        lignes = [float(s.y0) for s in (g['g10_h3'].layout.shapes or ())
                  if s.type == 'line']
        self.assertTrue(
            any(abs(v - lr * 100.0) < 1e-6 for v in lignes),
            'la ligne de référence ne vaut pas lr_apriori × 100 (%.4f) ; '
            'lignes tracées : %s' % (lr * 100.0, lignes))
        print('    OK C2-10 g10 : ligne de référence == lr_apriori × 100 '
              '= %.2f' % (lr * 100.0))

    def test_g11_les_courbes_sont_les_ultimates_publies(self):
        g, _, _, n3, _ = _figures()
        att = {
            'Dernière diagonale': n3['chain_ladder']['last_diagonale'],
            'Chain Ladder':       n3['chain_ladder']['ultimates'],
            'BF':                 n3['bf']['ultimates'],
            'Cape Cod':           n3['cape_cod']['ultimates'],
        }
        for lbl, src in att.items():
            np.testing.assert_allclose(
                _f(_tr(g['g11_ultimates'], lbl).y), _f(src), rtol=1e-9,
                err_msg='série %r' % lbl)
        diag = _f(att['Dernière diagonale'])
        for lbl in ('Chain Ladder', 'BF', 'Cape Cod'):
            ult = _f(_tr(g['g11_ultimates'], lbl).y)
            self.assertTrue(
                all(u >= d - 1.0 for u, d in zip(ult, diag)),
                'la courbe %r passe SOUS la diagonale déjà payée' % lbl)
        print('    OK C2-11 g11 : 4 séries == les ultimates publiés, aucune '
              'sous la diagonale')

    def test_g12_le_tornado_est_horizontal_et_mesure_les_ecarts_au_be(self):
        g, _, _, _, n4 = _figures()
        be = float(n4['best_estimate'])
        att = sorted(round(float(v) - be, 2)
                     for v in (n4.get('sensibilites') or {}).values())
        obs = []
        for t in g['g12_sensibilites'].data:
            self.assertEqual(t.orientation, 'h',
                             'un tornado tracé en vertical n\'est pas un '
                             'tornado')
            obs += [round(v, 2) for v in _f(t.x) if v]
        self.assertEqual(sorted(obs), [v for v in att if v],
                         'les barres ne sont pas les écarts au BE')
        print('    OK C2-12 g12 : %d écarts horizontaux == sensibilites − BE'
              % len(obs))

    def test_g13_chaque_courbe_est_une_ligne_du_triangle(self):
        g, C, _, _, _ = _figures()
        n, m = C.shape
        for i in range(n):
            k = min(n - i - 1, m - 1)
            obs = _f(_tr(g['g13_paiements'], str(i)).y)
            np.testing.assert_allclose(obs, _f(C[i, :k + 1]), rtol=1e-9,
                                       err_msg='ligne %d du triangle' % i)
            self.assertEqual(
                obs, sorted(obs),
                'la courbe %d décroît : un cumulé qui recule doit venir d\'un '
                'recours, pas d\'un tracé' % i)
        print('    OK C2-13 g13 : %d courbes == les lignes du triangle cumulé'
              % n)

    def test_g14_le_backtesting_est_l_ecart_projete_observe(self):
        g, _, _, n3, _ = _figures()
        res = (n3.get('backtesting') or {}).get('resultats') or {}
        for nom, cle in (('Horizon N-1', 'horizon_1'),
                         ('Horizon N-2', 'horizon_2')):
            annees = (res.get(cle) or {}).get('annees') or []
            t = _tr(g['g14_backtesting'], nom)
            np.testing.assert_allclose(
                _f(t.y), [float(a['ecart_pct']) for a in annees], rtol=1e-9,
                err_msg='horizon %r' % nom)
            self.assertEqual([str(v) for v in t.x],
                             [a['annee_label'] for a in annees],
                             'les points de %r ne sont pas alignés sur les '
                             'années qu\'ils datent' % nom)
        print('    OK C2-14 g14 : les 2 horizons == ecart_pct par année, '
              'étiquettes alignées')


# =============================================================================
#  T3 — LES DÉFAUTS CONSTATÉS EN C2, NON CORRIGÉS ICI
# =============================================================================

class T3_Defauts_Constates_A_Corriger_En_C3(unittest.TestCase):
    """⚠️ Chaque test énonce ce qui DEVRAIT être vrai.

    Le marqueur `expectedFailure` se démonte tout seul : quand le correctif
    arrive, le test réussit, unittest le compte en `unexpectedSuccess` et la
    campagne ÉCHOUE tant que le marqueur n'est pas retiré.

    ⚠️ LE DISPOSITIF A FONCTIONNÉ, ET C'EST ICI QU'ON LE VOIT. Le lot C3a a
    corrigé les deux faux zéros en faisant consommer aux livrables le
    référentiel `methodes_be` et sa garde `disponible` : la campagne est
    passée au rouge avec « unexpected successes=2 », et les deux marqueurs
    ont dû être retirés. Ils l'ont été — les deux tests ci-dessous sont
    désormais des verrous ordinaires.

    RESTE UN MARQUEUR : g7, dont l'étiquette sera réglée au lot C3b par le
    RETRAIT du graphique. ⚠️ ET CELUI-LÀ NE SE DÉMONTERA PAS TOUT SEUL :
    `expectedFailure` avale une erreur autant qu'un échec (vérifié — un
    `KeyError` y passe en silence). C'est `T1.test_les_quatorze_sont_produits`
    qui tombera quand le catalogue passera à 11, et forcera son retrait.
    """

    @unittest.expectedFailure
    def test_g7_le_quatrieme_segment_devrait_etre_le_scr(self):
        """GRAVITÉ 1 — le donut affiche DEUX « SCR » qui diffèrent de 33 %.

        Le segment porte l'étiquette « SCR (P99.5) » mais vaut P99.5 − P90,
        un INCRÉMENT de l'échelle des percentiles. Le vrai SCR de l'article
        115 (3·σ·V) est affiché au centre du MÊME donut, sous le MÊME mot.
        """
        g, _, _, _, n4 = _figures()
        p = g['g7_scr'].data[0]
        i = list(p.labels).index('SCR (P99.5)')
        self.assertAlmostEqual(float(p.values[i]),
                               float(n4['scr']['scr_provisions']), places=2)

    def test_g5_une_methode_indisponible_ne_devrait_pas_valoir_zero_euro(self):
        """CORRIGÉ AU LOT C3a — le marqueur `expectedFailure` a été retiré.

        `res_map.get(m, 0)` transformait « non calculable faute d'exposition »
        en « réserve de zéro euro », étiquette « 0€ » imprimée sur la barre.
        Le scénario sans primes est celui de l'oracle GenIns : ce n'était pas
        un cas de bord.

        g5 lit désormais `methodes_be.reserve()`, qui rend **None** et non
        zéro : une méthode exclue mais CALCULÉE reste tracée en grisé — c'est
        une information — et une méthode absente n'a plus de barre.
        """
        g, _, _, n3, _ = _figures(avec_primes=False)
        self.assertFalse(n3['bf']['disponible'])
        for lbl in ('Bornhuetter-Ferguson', 'Cape Cod'):
            try:
                t = _tr(g['g5_convergence'], lbl)
            except AssertionError:
                continue          # absente : c'est la bonne réponse
            self.fail('%r tracé à %s € alors que la méthode est indisponible'
                      % (lbl, _f(t.y)))

    def test_g11_une_methode_indisponible_ne_devrait_pas_etre_une_ligne_a_zero(self):
        """CORRIGÉ AU LOT C3a — le marqueur `expectedFailure` a été retiré.

        Sur un graphique « ultimates vs diagonale », deux séries plates à zéro
        affirmaient des ultimes INFÉRIEURS aux montants déjà payés. La liste
        `n3['bf']['ultimates']` n'est pas VIDE quand BF est indisponible :
        elle est pleine de zéros, donc le `if ult:` la laissait passer. La
        garde porte maintenant sur `disponible()`, pas sur la longueur.
        """
        g, _, _, n3, _ = _figures(avec_primes=False)
        self.assertFalse(n3['cape_cod']['disponible'])
        for lbl in ('BF', 'Cape Cod'):
            try:
                t = _tr(g['g11_ultimates'], lbl)
            except AssertionError:
                continue
            self.assertTrue(any(v for v in _f(t.y)),
                            '%r est une ligne plate à zéro' % lbl)


if __name__ == '__main__':
    unittest.main(verbosity=2)
