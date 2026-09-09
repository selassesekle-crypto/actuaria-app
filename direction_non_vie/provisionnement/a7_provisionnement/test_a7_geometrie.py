# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — LA GEOMETRIE DU TRIANGLE, ET CE QU'ELLE NE DOIT PAS DEPLACER
=============================================================================

 Le module supposait que l'indice de ligne et celui de colonne avancent au
 MEME PAS. Deux consequences mesurees, et elles n'ont pas la meme cause :

 · SURVENANCE ANNUELLE, DEVELOPPEMENT TRIMESTRIEL. Sur un 8x32 dont la
   reserve vraie est 3 316 654 EUR, le module lisait 36 cellules sur 144 et
   publiait 1 364 690 EUR -- **-58,9 %**. Preuve que les 108 autres
   n'etaient lues par personne : les multiplier par DIX ne deplacait pas un
   centime.

 · LE REMPLISSAGE. Un 6x6 pose dans une matrice 6x10 aux colonnes de queue
   vides fabriquait quatre facteurs de 1,0000 ; l'estimateur de queue les
   lisait comme des coefficients stabilises et retirait la queue.
   **tail 1,2624 -> 1,0, statut ROUGE -> VERT, Best Estimate -38,6 %**, sur
   les MEMES 21 cellules. Une reserve plus basse assortie d'un voyant plus
   vert.

 CE QUE CE FICHIER SCELLE, ET DANS QUEL ORDRE D'IMPORTANCE.

 T1 est le controle le plus important, et ce n'est pas celui du defaut :
 c'est celui de sa NON-CONTAGION. Un triangle dont le developpement ne
 depasse pas la survenance ne doit PAS bouger d'un euro -- c'est la forme de
 tous les dossiers d'aujourd'hui, et ils n'ont rien demande.

 ⚠️ POURQUOI L'AGREGATION ET NON LA LECTURE DU MASQUE : mesure faite, la
 route par masque rend le Best Estimate exact ET une incertitude absurde
 (CV 3 961 256 %, P90 CENT FOIS SOUS la moyenne, ecart-type bootstrap nul),
 parce que `mack.py` et `bootstrap_odp.py` portent leur propre frontiere --
 et parce que 31 facteurs ne tiennent pas dans 8 lignes d'origine. Le
 detail est en tete de `geometrie_triangle.py`.
=============================================================================
"""
import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement,
)
from direction_non_vie.provisionnement.a7_provisionnement.geometrie_triangle import (
    GeometrieRefusee,
    analyser_geometrie,
    longueurs_observees,
    pas_de_developpement,
)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS,
    RAA,
)

BASE, G = 100000.0, 0.04


def _triangle(n, m):
    """Triangle usuel n x m : la frontiere est a i + j < n."""
    inc = np.array([0.85 ** j for j in range(m)])
    C = np.array([np.cumsum(BASE * (1 + G * i) * inc) for i in range(n)])
    for i in range(n):
        C[i, max(0, n - i):] = 0.0
    return C


def _large(n, K, base=1_000_000.0, g=0.03):
    """n annees de survenance ANNUELLES, K periodes de developpement par an."""
    mq = n * K
    pat = np.array([0.88 ** (q / K) - 0.88 ** ((q + 1) / K) for q in range(mq)])
    pat = pat / pat.sum()
    ult = np.array([base * (1 + g) ** i for i in range(n)])
    C = np.zeros((n, mq))
    for i in range(n):
        v = K * (n - i)
        C[i, :v] = np.cumsum(ult[i] * pat[:v])
    return C


def _annuel_equivalent(n, K, base=1_000_000.0, g=0.03):
    """Le MEME portefeuille, mais decrit directement au pas annuel."""
    mq = n * K
    pat = np.array([0.88 ** (q / K) - 0.88 ** ((q + 1) / K) for q in range(mq)])
    pat = pat / pat.sum()
    ult = np.array([base * (1 + g) ** i for i in range(n)])
    inc = np.array([[ult[i] * pat[K * k:K * (k + 1)].sum() for k in range(n)]
                    for i in range(n)])
    C = np.zeros((n, n))
    for i in range(n):
        C[i, :n - i] = np.cumsum(inc[i, :n - i])
    return C


def _run(C, primes=False, **kw):
    src = np.asarray(C, dtype=float)
    d = dict(source=src, mode_declare='cumule', generer_graphiques=False,
             generer_word=False, generer_html=False, n_sim_bootstrap=40,
             seed=42)
    if primes:
        d['primes'] = np.full(src.shape[0], float(np.nanmean(src[:, 0])) * 8.0)
    d.update(kw)
    return AgentA7Provisionnement(verbose=False).run(**d)


def _be(r):
    return round(float((r.get('n4') or {}).get('best_estimate') or 0), 2)


# =============================================================================
#  T1 — CE QUI NE DOIT PAS BOUGER
# =============================================================================

class T1_Aucun_Dossier_Normal_Ne_Bouge(unittest.TestCase):
    """⚠️⚠️ LE CONTROLE LE PLUS IMPORTANT DU LOT, ET C'EST CELUI DE LA
    NON-CONTAGION. Corriger une forme que personne ne soumet ne vaut rien si
    le correctif touche celles que tout le monde soumet. L'analyse est donc
    ASYMETRIQUE par construction : `m <= n` n'est pas examine."""

    def test_un_triangle_dont_le_developpement_n_excede_pas_la_survenance_est_intact(self):
        for nom, C in (('RAA 10x10', np.asarray(RAA, float)),
                       ('GenIns', np.asarray(GENINS, float)),
                       ('carre 6x6', _triangle(6, 6)),
                       ('tronque 8x5', _triangle(8, 5))):
            geo = analyser_geometrie(C)
            self.assertFalse(
                geo['transforme'],
                '%s a ete TRANSFORME alors que son developpement n excede pas '
                'sa survenance' % nom)
            np.testing.assert_array_equal(
                np.asarray(geo['triangle'], float),
                np.asarray(C, float)[:, :geo['triangle'].shape[1]],
                'la matrice de %s a ete modifiee' % nom)
        print('OK GEO-1 : quatre formes normales traversent intactes')

    def test_les_montants_publies_des_references_sont_au_centime_les_memes(self):
        """⚠️ L'INTACTITUDE DE LA MATRICE NE SUFFIT PAS : c'est le MONTANT
        PUBLIE qui doit etre identique. Valeurs figees a la mesure du lot 12,
        avant l'existence de ce module."""
        for nom, C, expo, attendu in (
                ('RAA', RAA, False, 52135.21),
                ('RAA + exposition', RAA, True, 58105.79),
                ('GenIns', GENINS, False, 18680856.42),
                ('GenIns + exposition', GENINS, True, 17571608.66)):
            be = _be(_run(np.asarray(C, float), primes=expo))
            self.assertAlmostEqual(
                be, attendu, places=0,
                msg='%s : le Best Estimate a bouge, %.2f attendu %.2f — la '
                    'porte de geometrie touche un dossier qui ne la concerne '
                    'pas.' % (nom, be, attendu))
        print('OK GEO-2 : les quatre montants de reference sont au centime')


# =============================================================================
#  T2 — LE REMPLISSAGE NE CHANGE PLUS RIEN
# =============================================================================

class T2_Le_Remplissage(unittest.TestCase):

    def test_completer_un_triangle_de_colonnes_vides_ne_change_pas_le_be(self):
        C = _triangle(6, 6)
        D = np.zeros((6, 10))
        D[:, :6] = C
        self.assertTrue(np.array_equal(C[C != 0], D[D != 0]),
                        'les deux matrices ne portent pas les memes valeurs')
        a, b = _be(_run(C)), _be(_run(D))
        self.assertGreater(
            min(a, b), 0.0,
            'les deux Best Estimates sont nuls : ce controle comparerait deux '
            'echecs et passerait au vert. Mesure : sous une plantation qui '
            'faisait REFUSER les deux triangles, il est reste vert -- un '
            'controle qui compare sans exiger que le TRAVAIL AIT EU LIEU ne '
            'garde rien.')
        self.assertAlmostEqual(
            a, b, places=0,
            msg='le remplissage deplace le Best Estimate : %.2f contre %.2f. '
                'Les colonnes vides fabriquent des facteurs de 1,0000 que '
                'l estimateur de queue lit comme des coefficients stabilises.'
                % (a, b))
        print('OK GEO-3 : 6x6 et 6x10 complete rendent %.0f EUR' % a)

    def test_le_retrait_des_colonnes_vides_est_declare(self):
        """⚠️ UN RETRAIT SILENCIEUX RESTE UN RETRAIT. Le lecteur doit savoir
        que sa matrice n'a pas ete calculee telle qu'il l'a fournie."""
        D = np.zeros((6, 10))
        D[:, :6] = _triangle(6, 6)
        infos = analyser_geometrie(D)['infos']
        self.assertTrue(
            any('vide' in i for i in infos),
            'le retrait des colonnes vides n est pas declare : %s' % infos)
        print('OK GEO-4 : le retrait est declare')


# =============================================================================
#  T3 — L'AGREGATION EST EXACTE, DE BOUT EN BOUT
# =============================================================================

class T3_L_Agregation(unittest.TestCase):

    def test_le_triangle_large_rend_le_meme_be_que_son_equivalent_annuel(self):
        """⚠️ L'ORACLE EST UN TEMOIN, PAS UNE VALEUR FIGEE : on compare deux
        descriptions du MEME portefeuille. Un test qui gelerait un montant ne
        distinguerait pas « exact » de « stable »."""
        large = _be(_run(_large(8, 4)))
        annuel = _be(_run(_annuel_equivalent(8, 4)))
        self.assertAlmostEqual(
            large, annuel, places=0,
            msg='le 8x32 agrege rend %.2f la ou le 8x8 annuel equivalent rend '
                '%.2f : l agregation n est pas exacte.' % (large, annuel))
        self.assertGreater(large, 0.0, 'le triangle large ne produit rien')
        print('OK GEO-5 : 8x32 et 8x8 equivalent rendent %.0f EUR' % large)

    def test_le_pas_lu_est_le_bon_et_l_agregation_est_declaree(self):
        geo = analyser_geometrie(_large(8, 4))
        self.assertEqual(geo['pas'], 4, 'le pas lu n est pas 4')
        self.assertTrue(geo['transforme'])
        self.assertEqual(geo['triangle'].shape, (8, 8),
                         'la forme agregee n est pas 8x8')
        self.assertTrue(any('agrégé' in i or 'agrege' in i
                            for i in geo['infos']),
                        'l agregation n est pas declaree : %s' % geo['infos'])
        self.assertTrue(any('écoulement' in i for i in geo['infos']),
                        'la perte de finesse du profil n est pas declaree')
        print('OK GEO-6 : pas=4, 8x32 -> 8x8, et les deux pertes sont dites')

    def test_un_arrete_en_milieu_de_sous_periode_declare_ce_qu_il_ecarte(self):
        """⚠️ L'ASSIETTE EST LE SEUIL, DES DEUX COTES : en fin d'annee il n'y
        a rien a declarer, et le declarer quand meme serait du bruit."""
        C = _large(8, 4)
        # on recule l'arrete de deux trimestres : la derniere sous-periode de
        # chaque ligne devient incomplete
        L = longueurs_observees(C)
        D = C.copy()
        for i in range(8):
            D[i, max(0, L[i] - 2):] = 0.0
        infos_mi = analyser_geometrie(D)['infos']
        infos_fin = analyser_geometrie(C)['infos']
        self.assertTrue(
            any('sous-période incomplète' in i for i in infos_mi),
            'un arrete en milieu de sous-periode n annonce pas ce qu il '
            'ecarte : %s' % infos_mi)
        self.assertFalse(
            any('sous-période incomplète' in i for i in infos_fin),
            'un arrete en FIN de sous-periode annonce une perte qui n existe '
            'pas : %s' % infos_fin)
        print('OK GEO-7 : la perte est annoncee en milieu, tue en fin')


# =============================================================================
#  T4 — CE QUI EST REFUSE L'EST NOMMEMENT
# =============================================================================

class T4_Les_Refus(unittest.TestCase):

    def _refus(self, C):
        with self.assertRaises(GeometrieRefusee) as ctx:
            analyser_geometrie(C)
        return str(ctx.exception)

    def test_un_rectangle_entierement_observe_n_a_pas_de_futur(self):
        inc = np.array([0.85 ** j for j in range(10)])
        C = np.array([np.cumsum(BASE * (1 + G * i) * inc) for i in range(6)])
        self.assertEqual(pas_de_developpement(C), 0)
        m = self._refus(C)
        self.assertIn('entièrement observé', m)
        print('OK GEO-8 : rectangle plein refuse — %s' % m[:64])

    def test_des_longueurs_irregulieres_ne_sont_pas_un_triangle(self):
        C = np.array([np.cumsum(BASE * (1 + G * i)
                                * np.array([0.85 ** j for j in range(10)]))
                      for i in range(6)])
        for i, v in enumerate((10, 4, 9, 2, 7, 3)):
            C[i, v:] = 0.0
        self.assertIsNone(pas_de_developpement(C))
        m = self._refus(C)
        self.assertIn('pas constant', m)
        print('OK GEO-9 : longueurs irregulieres refusees')

    def test_le_refus_traverse_l_agent_et_marque_le_dossier(self):
        """⚠️ UN REFUS QUI N'ATTEINT PAS LE DOSSIER N'EST PAS UN REFUS. Le
        contrat degrade d'`agent.run()` doit porter l echec, et le lot 12 a
        ferme la porte d export sur ce vide."""
        inc = np.array([0.85 ** j for j in range(10)])
        C = np.array([np.cumsum(BASE * (1 + G * i) * inc) for i in range(6)])
        r = _run(C)
        self.assertFalse(r.get('success'),
                         'un triangle refuse produit tout de meme un dossier')
        self.assertEqual(r.get('statut_rag'), 'ROUGE')
        self.assertIn('observé', str(r.get('erreur') or ''),
                      'le motif du refus n atteint pas le dossier : %r'
                      % r.get('erreur'))
        print('OK GEO-10 : le refus atteint le dossier, RAG ROUGE')

    def test_un_triangle_large_LEGITIME_n_est_pas_refuse(self):
        """⚠️ LE MIROIR. Un garde-fou qui refuse tout ne garde rien : la forme
        que ce lot existe pour traiter doit PASSER."""
        r = _run(_large(8, 4))
        self.assertTrue(r.get('success'),
                        'le triangle annuel x trimestriel est refuse alors '
                        'que c est precisement le cas a traiter')
        self.assertGreater(_be(r), 0.0)
        print('OK GEO-11 : le 8x32 legitime passe et publie %.0f EUR' % _be(r))


# =============================================================================
#  T5 — LA LECTURE DU PAS
# =============================================================================

class T5_La_Lecture_Du_Pas(unittest.TestCase):

    def test_un_trou_interieur_ne_rend_pas_le_pas_illisible(self):
        """⚠️⚠️ COMPTER LES CELLULES NON NULLES PARAIT EQUIVALENT ET NE L'EST
        PAS. Une annee sans aucun paiement au milieu du developpement fait
        perdre une unite a la ligne : le pas devient illisible et un dossier
        parfaitement normal serait refuse. On prend l INDEX DE LA DERNIERE
        cellule connue, pas leur NOMBRE."""
        C = np.asarray(RAA, float).copy()
        C[2, 3] = 0.0
        self.assertEqual(longueurs_observees(C)[2], 8,
                         'la longueur de la ligne trouee est mal lue')
        self.assertEqual(pas_de_developpement(C), 1,
                         'un trou interieur rend le pas illisible')
        self.assertFalse(analyser_geometrie(C)['transforme'])
        print('OK GEO-12 : un trou interieur laisse le pas a 1')

    def test_le_pas_vaut_un_sur_les_triangles_du_depot(self):
        """La regle GENERALISE l'existant : sur la forme usuelle elle rend 1,
        et 1 est le cas ou rien ne change."""
        for nom, C in (('RAA', RAA), ('GenIns', GENINS)):
            self.assertEqual(pas_de_developpement(np.asarray(C, float)), 1,
                             '%s ne lit pas un pas de 1' % nom)
        print('OK GEO-13 : pas = 1 sur les deux triangles de reference')


if __name__ == '__main__':
    unittest.main(verbosity=2)
