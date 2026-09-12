# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — LA GEOMETRIE SE JUGE PAR LES DEUX PORTES D'ENTREE
=============================================================================

 CE FICHIER EXISTE PARCE QU'UNE COUVERTURE ETAIT ASYMETRIQUE.

 Mesure du 11/09/2026 : les treize tests de `test_a7_geometrie.py`
 construisent tous leur dossier par `source=np.asarray(C)` — une MATRICE.
 Aucun ne passe par un tableau LONG, qui est pourtant la forme qu'un assureur
 fournit. Or la construction depuis un tableau long RETAILLE le triangle AVANT
 que la porte de geometrie ne le voie : la porte lisait alors une frontiere
 fabriquee par l'etape precedente, et concluait que tout allait bien.

 LE CAS QUI MANQUAIT, ET IL N'EST PAS EXOTIQUE : un portefeuille en RUN-OFF
 ENTIEREMENT OBSERVE — toutes les lignes de meme longueur. Les six formes de
 `test_a7_couture_ingestion` couvrent deux carres, trois tronques et un
 infra-annuel ; aucune n'est un run-off plein. C'est precisement la forme dont
 le pas est ILLISIBLE (les ecarts de longueur valent tous zero), et ou le
 repli historique `i + j >= n` mordait sur des cellules renseignees :

     4x4 en run-off ......... 6 cellules sur 16 effacees, 1 268 de cumul perdu
     6x6, 6 750 EUR payes, IBNR VRAI = 0
         par matrice cumulee declaree ... ROUGE, Best Estimate ABSENT
         par table longue, memes euros .. AMBRE, BE 1 554 EUR, SCR 513 EUR

 ⚠️ CE FICHIER NE COMPARE PAS A UN ORACLE, IL COMPARE DEUX CHEMINS. Une
 valeur figee dirait « stable » ; cette identite dit « le meme portefeuille
 rend le meme dossier, quelle que soit la facon dont on le decrit ».
=============================================================================
"""
import logging
import unittest
import warnings

import numpy as np
import pandas as pd

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement,
)

#: ⚠️⚠️ ON NE COUPE PAS LES JOURNAUX A L IMPORT. Le correctif recu posait
#: `logging.disable(logging.CRITICAL)` en tete de module. Le depot
#: l INTERDIT, et pour une raison mesuree : `core/test_journaux_importables
#: .py::F5_LeDepotEntier` echoue sur ce motif, et `test_a7_ibrahim` l.347
#: rappelle pourquoi — un `logging.disable(CRITICAL)` de script de
#: verification a deja MASQUE un `logger.error` reel et laisse une
#: regression survivre DEUX lots (export Excel retombe a 0 octet).
#: La mise en sourdine reste, mais BORNEE a la duree des tests de ce
#: fichier : l import, lui, ne touche plus a la configuration globale.
_SOURDINE = None


def _usuel(n, m):
    """Zone connue i + j < n — le triangle de tous les jours."""
    inc = np.zeros((n, m))
    for i in range(n):
        for j in range(min(m, n - i)):
            inc[i, j] = 100000.0 * (1 + 0.04 * i) * (0.85 ** j)
    return inc


def _run_off(n, m):
    """⚠️ LA FORME QUI MANQUAIT : toutes les lignes developpees jusqu'au bout.

    Un portefeuille clos, dont chaque annee de survenance a fini de se
    developper. Son IBNR VRAI est nul, et son pas de developpement est
    ILLISIBLE — les ecarts de longueur valent tous zero."""
    inc = np.zeros((n, m))
    for i in range(n):
        for j in range(m):
            inc[i, j] = 1000.0 * (1 + 0.05 * i) * (0.80 ** j)
    return inc


def _infra(n=8, K=4, base=1_000_000.0, g=0.03):
    """Survenance ANNUELLE, developpement TRIMESTRIEL."""
    mq = n * K
    pat = np.array([0.88 ** (q / K) - 0.88 ** ((q + 1) / K) for q in range(mq)])
    pat = pat / pat.sum()
    inc = np.zeros((n, mq))
    for i in range(n):
        v = K * (n - i)
        inc[i, :v] = base * (1 + g) ** i * pat[:v]
    return inc


def _cumuler(inc):
    C = np.zeros_like(inc)
    for i in range(inc.shape[0]):
        c = np.where(inc[i] != 0.0)[0]
        if c.size:
            C[i, :int(c[-1]) + 1] = np.cumsum(inc[i, :int(c[-1]) + 1])
    return C


def _tableau(inc, an0=2018):
    """Le MEME portefeuille, en tableau de sinistres."""
    return pd.DataFrame([
        {'annee_survenance': an0 + i, 'annee_developpement': j,
         'montant_paye': float(inc[i, j])}
        for i in range(inc.shape[0]) for j in range(inc.shape[1])
        if inc[i, j] != 0.0])


def _dossier(**kw):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return AgentA7Provisionnement(verbose=False).run(
            generer_graphiques=False, generer_word=False, generer_html=False,
            n_sim_bootstrap=20, seed=42, **kw)


def _resume(r):
    """Ce qu'un lecteur voit : a-t-il abouti, de quelle couleur, pour combien."""
    be = (r.get('n4') or {}).get('best_estimate')
    return (bool(r.get('success')),
            str(r.get('statut_rag')),
            None if be is None else round(float(be), 2))


FORMES = (
    ('carre 6x6', _usuel(6, 6)),
    ('tronque 8x5', _usuel(8, 5)),
    ('tronque 14x8', _usuel(14, 8)),
    ('infra-annuel 8x32', _infra()),
    # ⚠️ LA FORME QUE LA COUVERTURE N'AVAIT PAS.
    ('run-off plein 4x4', _run_off(4, 4)),
    ('run-off plein 6x6', _run_off(6, 6)),
)


class T_Les_Deux_Portes_Rendent_Le_Meme_Dossier(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        global _SOURDINE
        _SOURDINE = logging.root.manager.disable
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(_SOURDINE)

    def test_le_verdict_ne_depend_pas_de_la_facon_de_decrire_le_portefeuille(
            self):
        """⚠️⚠️ LA PROPRIETE CENTRALE, ET ELLE N'A PAS D'ORACLE. Le meme
        portefeuille, decrit en matrice cumulee ou en tableau de sinistres,
        doit rendre le MEME dossier : meme aboutissement, meme couleur, meme
        Best Estimate au centime."""
        ecarts = []
        for nom, inc in FORMES:
            a = _resume(_dossier(source=_cumuler(inc), mode_declare='cumule'))
            b = _resume(_dossier(source=_tableau(inc)))
            if a != b:
                ecarts.append('%-20s matrice %r   tableau %r' % (nom, a, b))
        self.assertEqual(
            ecarts, [],
            'Le meme portefeuille rend deux dossiers selon la porte '
            'd entree :\n  ' + '\n  '.join(ecarts))
        print('    OK GEO2-1 %d formes, les deux portes s accordent'
              % len(FORMES))

    def test_un_run_off_entierement_observe_est_refuse_PAR_LES_DEUX_PORTES(
            self):
        """⚠️⚠️ LE CAS EXACT DU CONSTAT D-A. Un portefeuille clos n'a pas de
        futur : `analyser_geometrie` le refuse — « rectangle entierement
        observe ». Par la table longue, la construction le retaillait AVANT
        que la porte ne le voie, et le dossier sortait AMBRE avec une reserve
        sur un IBNR vrai NUL."""
        inc = _run_off(6, 6)
        for porte, kw in (('matrice cumulee',
                           dict(source=_cumuler(inc), mode_declare='cumule')),
                          ('tableau long', dict(source=_tableau(inc)))):
            r = _dossier(**kw)
            with self.subTest(porte=porte):
                self.assertFalse(
                    r.get('success'),
                    '%s : un run-off entierement observe produit un dossier '
                    'alors qu il n a pas de zone future' % porte)
                self.assertEqual(r.get('statut_rag'), 'ROUGE')
                self.assertIsNone(
                    (r.get('n4') or {}).get('best_estimate'),
                    '%s : une reserve est publiee sur un portefeuille dont '
                    'l IBNR vrai est NUL' % porte)
        print('    OK GEO2-2 le run-off plein est refuse par les deux portes')

    def test_aucune_cellule_enregistree_n_est_effacee_par_la_construction(
            self):
        """⚠️ LA METHODE DU MODULE LUI-MEME : si multiplier par dix des
        cellules FOURNIES ne deplace pas la charge lue, personne ne les lit.

        On mesure la charge que la construction RETIENT, pas le Best Estimate :
        un dossier refuse n'en a pas, et c'est justement le cas qu'on teste."""
        from direction_non_vie.services.nv_triangle_construction import (
            construire_triangles,
        )
        for nom, inc in (('run-off plein 4x4', _run_off(4, 4)),
                         ('run-off plein 6x6', _run_off(6, 6)),
                         ('infra-annuel 8x32', _infra())):
            fourni = float(inc.sum())
            t = construire_triangles(_tableau(inc))
            C = np.asarray(getattr(t, 'paiements', None)
                           if hasattr(t, 'paiements') else t, dtype=float)
            # Charge lue = derniere valeur cumulee non nulle de chaque ligne.
            lue = 0.0
            for i in range(C.shape[0]):
                nz = np.where(C[i] != 0.0)[0]
                if nz.size:
                    lue += float(C[i, int(nz[-1])])
            with self.subTest(forme=nom):
                self.assertAlmostEqual(
                    lue, fourni, places=2,
                    msg='%s : %.2f EUR fournis, %.2f EUR retenus par la '
                        'construction — %.1f %% des montants sont effaces '
                        'avant que quiconque les voie'
                        % (nom, fourni, lue, 100.0 * (1 - lue / fourni)))
        print('    OK GEO2-3 aucune charge fournie n est effacee')


if __name__ == '__main__':
    unittest.main(verbosity=1)
