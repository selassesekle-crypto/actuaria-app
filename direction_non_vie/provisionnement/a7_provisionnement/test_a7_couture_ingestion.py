# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — LA COUTURE ENTRE L'INGESTION ET LE CALCUL
=============================================================================

 LE FILET QUI MANQUAIT, ET LE RELEVE QUI LE DIT. Sur les 47 fichiers de test
 d'A7 : **104 appels a `run()`, dont ZERO part d'un tableau de sinistres** ;
 `annee_developpement`, `montant_paye` et `preparer_pour_agent` n'apparaissent
 dans AUCUN d'eux. Les deux moities du pipeline sont testees separement et ne
 se rencontrent nulle part. C'est la reponse a « comment 1 025 tests verts
 ont-ils pu laisser passer -52,4 % » : ils sont bons, ils ne regardent pas la.

 CE QUE CE FICHIER SCELLE — trois defauts d'une seule cause.

 · Le masque `i + j >= n` de `_cumuler_et_masquer` SUPPOSAIT un pas de
   developpement egal au pas de survenance. Sur 8 annees annuelles
   developpees en 32 trimestres — une table de sinistres ordinaire — il
   mettait a ZERO **108 des 144 cellules** renseignees AVANT que quiconque
   puisse les voir. Mesure : paiements lus **1 768 070 EUR** au lieu de
   **5 575 682 EUR**, Best Estimate **-52,4 %**. La porte de geometrie, en
   aval, lisait alors « pas = 1, rien a signaler » : la perte avait eu lieu
   en amont et elle ne pouvait pas la voir.

 · `_pivot_long` elargissait l'axe de developpement jusqu'a la HAUTEUR du
   triangle. Les colonnes ajoutees n'etaient renseignees par aucune ligne, le
   masque ne les couvrait pas, et `np.cumsum` y RECOPIAIT la derniere valeur
   connue. Trois facteurs de 1,0000 etaient fabriques, la queue tombait de
   1,2233 a 1,0 et le statut de ROUGE a VERT. Mesure : **-46,5 %** sur un
   8x5, **-55,8 %** sur un 12x6 — une reserve plus basse assortie d'un
   voyant plus vert.

 · `_diagonale_payee` situait la derniere cellule connue par `min(n-i-1,
   m-1)`, une regle de FORME. Sur un triangle annuel x trimestriel elle lit
   le trimestre 7-i au lieu du trimestre 4(8-i)-1 — en plein developpement,
   la ou la provision dossier est encore lourde. Mesure en base charges :
   provisions dossier **+95,3 %**.

 ⚠️⚠️ CE QUE CE FICHIER VERIFIE N'EST PAS UN MONTANT, C'EST UNE IDENTITE.
 Le meme portefeuille, decrit de deux facons, doit rendre le meme Best
 Estimate. Un test qui figerait un montant ne distinguerait pas « juste » de
 « stable » ; celui-ci compare deux chemins et n'a besoin d'aucun oracle.

 ⚠️ ET LE CONTROLE LE PLUS IMPORTANT N'EST PAS CELUI DU DEFAUT : c'est
 T4, la non-contagion. Un correctif de la porte d'entree ne doit pas
 deplacer un euro sur les dossiers au pas usuel, qui sont tous les dossiers
 d'aujourd'hui.
=============================================================================
"""
import re
import unittest

import numpy as np
import pandas as pd

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement,
)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS,
    RAA,
)
from direction_non_vie.services.nv_triangle_construction import (
    _cumuler_et_masquer,
    pas_de_developpement_observe,
)
from direction_non_vie.services.nv_triangle_projection import (
    derniere_diagonale_observee,
)

#: Les quatre montants publies des dossiers de reference, figes AVANT ce lot.
FIGES = {
    'RAA': 52135.21,
    'RAA + exposition': 58105.79,
    'GenIns': 18680856.42,
    'GenIns + exposition': 17571608.66,
}


def _triangle_usuel(n, m):
    """Increments d'un triangle au pas usuel : la zone connue est i + j < n."""
    inc = np.zeros((n, m))
    for i in range(n):
        for j in range(min(m, n - i)):
            inc[i, j] = 100000.0 * (1 + 0.04 * i) * (0.85 ** j)
    return inc


def _triangle_infra_annuel(n=8, K=4, base=1_000_000.0, g=0.03):
    """n annees de survenance ANNUELLES, K periodes de developpement par an."""
    mq = n * K
    pat = np.array([0.88 ** (q / K) - 0.88 ** ((q + 1) / K) for q in range(mq)])
    pat = pat / pat.sum()
    ult = np.array([base * (1 + g) ** i for i in range(n)])
    inc = np.zeros((n, mq))
    for i in range(n):
        v = K * (n - i)
        inc[i, :v] = ult[i] * pat[:v]
    return inc


def _cumuler(inc):
    C = np.zeros_like(inc)
    for i in range(inc.shape[0]):
        c = np.where(inc[i] != 0.0)[0]
        if c.size:
            C[i, :int(c[-1]) + 1] = np.cumsum(inc[i, :int(c[-1]) + 1])
    return C


def _tableau(inc, an0=2018):
    """Le MEME portefeuille en tableau de sinistres — la forme qu'un assureur
    fournit, et celle qu'aucun test d'A7 n'employait."""
    return pd.DataFrame([
        {'annee_survenance': an0 + i, 'annee_developpement': j,
         'montant_paye': float(inc[i, j])}
        for i in range(inc.shape[0]) for j in range(inc.shape[1])
        if inc[i, j] != 0.0])


def _be(**kw):
    r = AgentA7Provisionnement(verbose=False).run(
        generer_graphiques=False, generer_word=False, generer_html=False,
        n_sim_bootstrap=30, seed=42, **kw)
    return round(float((r.get('n4') or {}).get('best_estimate') or 0), 2)


# =============================================================================
#  T1 — LE MEME PORTEFEUILLE, DEUX DESCRIPTIONS, UN SEUL BEST ESTIMATE
# =============================================================================

class T1_La_Couture(unittest.TestCase):
    """⚠️ AUCUN ORACLE ICI, ET C'EST VOULU : on compare deux CHEMINS. Une
    valeur figee dirait « stable » ; cette identite dit « juste »."""

    FORMES = (('carre 6x6', _triangle_usuel(6, 6)),
              ('carre 10x10', _triangle_usuel(10, 10)),
              ('tronque 8x5', _triangle_usuel(8, 5)),
              ('tronque 12x6', _triangle_usuel(12, 6)),
              ('tronque 14x8', _triangle_usuel(14, 8)),
              ('infra-annuel 8x32', _triangle_infra_annuel()))

    def test_matrice_cumulee_et_tableau_rendent_le_meme_best_estimate(self):
        ecarts = []
        for nom, inc in self.FORMES:
            a = _be(source=_cumuler(inc), mode_declare='cumule')
            b = _be(source=_tableau(inc))
            self.assertGreater(
                min(a, b), 0.0,
                '%s : un des deux chemins ne produit rien — ce controle '
                'comparerait deux echecs et passerait au vert.' % nom)
            e = 100.0 * (b - a) / a
            if abs(e) > 0.001:
                ecarts.append('%s : matrice %.2f, tableau %.2f (%+.2f %%)'
                              % (nom, a, b, e))
        self.assertEqual(
            ecarts, [],
            'Le meme portefeuille rend deux Best Estimate selon la facon dont '
            'il est decrit :\n  ' + '\n  '.join(ecarts))
        print('OK COUT-1 : %d formes, matrice et tableau alignes'
              % len(self.FORMES))

    def test_la_matrice_incrementale_est_alignee_elle_aussi(self):
        """⚠️ TROISIEME CHEMIN D'ENTREE, ET IL PASSAIT PAR LE MEME MASQUE.
        L'oublier serait l'assiette a moitie."""
        inc = _triangle_infra_annuel()
        a = _be(source=_cumuler(inc), mode_declare='cumule')
        c = _be(source=inc.copy(), mode_declare='incremental')
        self.assertAlmostEqual(
            a, c, places=0,
            msg='la matrice INCREMENTALE rend %.2f la ou la cumulee rend %.2f'
                % (c, a))
        print('OK COUT-2 : le chemin incremental est aligne (%.0f EUR)' % a)


# =============================================================================
#  T2 — CE QUI EST OBSERVE EST LU
# =============================================================================

class T2_La_Donnee_Est_Lue(unittest.TestCase):
    """⚠️ LA METHODE DU MODULE LUI-MEME : si multiplier par dix des cellules
    OBSERVEES ne deplace pas le Best Estimate, personne ne les lit."""

    def test_perturber_au_dela_de_l_ancienne_frontiere_deplace_le_be(self):
        inc = _triangle_infra_annuel()
        n = inc.shape[0]
        d = inc.copy()
        k = 0
        for i in range(n):
            for j in range(inc.shape[1]):
                if inc[i, j] != 0.0 and i + j >= n:
                    d[i, j] *= 10.0
                    k += 1
        self.assertGreater(k, 0, 'aucune cellule hors de l ancienne frontiere')
        a = _be(source=_tableau(inc))
        b = _be(source=_tableau(d))
        self.assertGreater(
            abs(b - a), 1.0,
            'x10 sur %d cellules OBSERVEES ne deplace pas le Best Estimate : '
            'elles ne sont lues par personne.' % k)
        print('OK COUT-3 : x10 sur %d cellules deplace %+.0f EUR' % (k, b - a))


# =============================================================================
#  T3 — LES DEUX HELPERS, LUS DANS LA DONNEE
# =============================================================================

class T3_Les_Helpers(unittest.TestCase):

    def test_le_masque_a_pas_1_est_litteralement_l_ancien(self):
        """⚠️ CE N'EST PAS UNE PROMESSE, C'EST LA MEME INEGALITE REECRITE :
        pour pas = 1, `j >= pas*(n-i)` EST `i + j >= n`. Verifie, pas affirme."""
        rng = np.random.default_rng(7)
        div = tot = 0
        for n in range(2, 25):
            m = 30
            inc = np.zeros((n, m))
            for i in range(n):
                for j in range(min(m, n - i)):
                    inc[i, j] = float(rng.integers(1, 10_000))
            neuf = _cumuler_et_masquer(inc)
            anc = np.cumsum(inc, axis=1)
            for i in range(n):
                for j in range(m):
                    if i + j >= n:
                        anc[i, j] = 0.0
            tot += n * m
            div += int(np.sum(anc != neuf))
        self.assertEqual(div, 0,
                         '%d divergences sur %d positions a pas = 1' % (div, tot))
        print('OK COUT-4 : %d positions, 0 divergence a pas = 1' % tot)

    def test_le_pas_se_lit_et_refuse_de_conclure_quand_il_ne_sait_pas(self):
        self.assertEqual(pas_de_developpement_observe(_triangle_usuel(8, 8)), 1)
        self.assertEqual(pas_de_developpement_observe(_triangle_infra_annuel()), 4)
        # ⚠️ LE ZERO EST UN REFUS DE CONCLURE : l'appelant retombe alors sur la
        # regle historique. Une geometrie illisible ne doit pas changer le
        # comportement d'un dossier qui marche aujourd'hui.
        irr = _triangle_usuel(6, 10)
        irr[2, :] = 0.0
        irr[2, 0] = 42.0
        self.assertEqual(pas_de_developpement_observe(irr), 0)
        print('OK COUT-5 : pas = 1 / 4 / 0 (refus de conclure)')

    def test_la_derniere_cellule_connue_egale_la_position_au_pas_usuel(self):
        """⚠️ SUR UN TRIANGLE AU PAS USUEL, LA DERNIERE CELLULE CONNUE **EST**
        CELLE DE LA POSITION `n-1-i` : la zone future y vaut exactement zero."""
        div = tot = 0
        for n in range(2, 21):
            for m in range(2, 21):
                C = _cumuler(_triangle_usuel(n, m))
                anc = np.array([float(C[i, min(n - i - 1, m - 1)])
                                for i in range(n)])
                tot += n
                div += int(np.sum(anc != derniere_diagonale_observee(C)))
        self.assertEqual(div, 0,
                         '%d divergences sur %d positions' % (div, tot))
        print('OK COUT-6 : %d positions, la lecture egale la position' % tot)


# =============================================================================
#  T4 — CE QUI NE DOIT PAS BOUGER
# =============================================================================

class T4_Non_Contagion(unittest.TestCase):
    """⚠️⚠️ LE CONTROLE LE PLUS IMPORTANT DU LOT. Corriger la porte d'entree
    pour une forme que personne ne soumet ne vaut rien si le correctif deplace
    un euro sur celles que tout le monde soumet."""

    def test_les_quatre_montants_de_reference_sont_au_centime_les_memes(self):
        for nom, C, expo in (('RAA', RAA, False),
                             ('RAA + exposition', RAA, True),
                             ('GenIns', GENINS, False),
                             ('GenIns + exposition', GENINS, True)):
            src = np.asarray(C, float)
            kw = dict(source=src, mode_declare='cumule')
            if expo:
                kw['primes'] = np.full(src.shape[0],
                                       float(np.nanmean(src[:, 0])) * 8.0)
            be = _be(**kw)
            self.assertAlmostEqual(
                be, FIGES[nom], places=0,
                msg='%s : le Best Estimate a bouge, %.2f attendu %.2f — la '
                    'correction de la porte d entree touche un dossier au pas '
                    'usuel.' % (nom, be, FIGES[nom]))
        print('OK COUT-7 : les quatre montants de reference sont au centime')

    def test_la_charge_a_date_ne_depend_pas_de_la_finesse_du_developpement(self):
        """⚠️⚠️ CE CONTROLE MANQUAIT, ET C'EST UNE PLANTATION QUI L'A DIT.
        `_diagonale_payee` et `_provisions_dossier` situaient la derniere
        cellule connue par `min(n-i-1, m-1)` — une regle de FORME. Elle ne mord
        qu'en BASE CHARGES, que le reste de ce fichier n'exercait pas : le
        plant qui retablissait la regle de position laissait les huit
        controles au VERT.

        Mesure du defaut, meme portefeuille decrit deux fois : provisions
        dossier 1 160 829 EUR en description annuelle contre 2 266 798 EUR en
        description trimestrielle, soit +95,3 % sur un chiffre de bilan."""
        n, K, base, g = 8, 4, 1_000_000.0, 0.03
        mq = n * K
        pat = np.array([0.88 ** (q / K) - 0.88 ** ((q + 1) / K)
                        for q in range(mq)])
        pat = pat / pat.sum()
        ult = np.array([base * (1 + g) ** i for i in range(n)])
        inc_q = np.array([[ult[i] * pat[q] for q in range(mq)]
                          for i in range(n)])
        paye_q = np.zeros((n, mq))
        for i in range(n):
            v = K * (n - i)
            paye_q[i, :v] = np.cumsum(inc_q[i, :v])
        chrg_q = paye_q.copy()
        for i in range(n):
            for q in range(K * (n - i)):
                chrg_q[i, q] = paye_q[i, q] + ult[i] * (
                    1.0 - pat[:q + 1].sum()) * 0.35
        # le MEME portefeuille, decrit au pas annuel
        inc_a = np.array([[inc_q[i, K * k:K * (k + 1)].sum() for k in range(n)]
                          for i in range(n)])
        paye_a = np.zeros((n, n))
        for i in range(n):
            paye_a[i, :n - i] = np.cumsum(inc_a[i, :n - i])
        chrg_a = np.zeros((n, n))
        for i in range(n):
            for k in range(n - i):
                chrg_a[i, k] = chrg_q[i, K * k + (K - 1)]

        def _prov(paye, chrg):
            r = AgentA7Provisionnement(verbose=False).run(
                source=paye, triangle_engage=chrg, mode_declare='cumule',
                triangle_reference='charges', generer_graphiques=False,
                generer_word=False, generer_html=False, n_sim_bootstrap=20,
                seed=42)
            ligne = next((str(i) for i in (r['n1'].get('infos') or [])
                          if 'provisions dossier' in str(i)), None)
            self.assertIsNotNone(
                ligne, 'la ligne des provisions dossier a disparu : ce '
                       'controle comparerait deux absences.')
            return float(re.sub(r'[^0-9]', '',
                                ligne.split('€')[0].split(':')[1]))

        a, b = _prov(paye_a, chrg_a), _prov(paye_q, chrg_q)
        self.assertGreater(min(a, b), 0.0,
                           'un des deux cotes ne publie aucune provision')
        ecart = 100.0 * (b - a) / a
        self.assertLess(
            abs(ecart), 0.5,
            'Les provisions dossier dependent de la FINESSE du developpement : '
            '%.0f EUR en description annuelle contre %.0f EUR en '
            'trimestrielle (%+.1f %%). La charge a date est lue a une '
            'position, pas dans la donnee.' % (a, b, ecart))
        print('OK COUT-9 : provisions dossier %.0f EUR, ecart %+.2f %%'
              % (a, ecart))

    def test_un_tableau_tronque_ne_fabrique_plus_de_colonnes(self):
        """⚠️ `_pivot_long` elargissait l'axe jusqu'a la HAUTEUR. Les colonnes
        ajoutees n'etaient renseignees par aucune ligne, et `np.cumsum` y
        recopiait la derniere valeur connue."""
        from direction_non_vie.services.nv_triangle import preparer_pour_agent
        for n, m in ((8, 5), (12, 6), (14, 8)):
            C, _, _, _ = preparer_pour_agent(source=_tableau(_triangle_usuel(n, m)))
            self.assertEqual(
                np.asarray(C).shape[1], m,
                'un tableau %dx%d sort en %s : l axe a ete elargi'
                % (n, m, np.asarray(C).shape))
        print('OK COUT-8 : trois tableaux tronques gardent leur largeur')


if __name__ == '__main__':
    unittest.main(verbosity=2)
