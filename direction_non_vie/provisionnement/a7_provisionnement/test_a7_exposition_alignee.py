# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — L'EXPOSITION EST RATTACHEE A SON ANNEE, JAMAIS A SA POSITION
=============================================================================

 Une table de primes etait agregee par annee de survenance puis APLATIE en
 vecteur positionnel. `_normaliser_primes` le tronquait ou le completait de
 zeros sans jamais rapprocher les annees du repere du triangle.

 · Une annee MANQUANTE decalait toute l'exposition a partir d'elle. L'alerte
   emise annoncait « vecteur plus court », ce qui fait croire que seule la
   DERNIERE annee est touchee : elle etait PIRE qu'aucune alerte.
 · Une table COMMENCANT PLUS TOT etait tronquee EN SILENCE.

 MESURE SUR RAA, chaine de production complete, primes plausibles :

     table                 BE       BF    CapeCod   alerte
     COMPLETE          71 298   90 462    76 406    —
     TROU en 1985      54 072   59 826    50 255    trompeuse   (BE −24,2 %)
     COMMENCE 1979     77 306   99 643    80 140    AUCUNE      (BE +8,4 %)

 ⚠️⚠️ LE SENS DE L'ERREUR N'EST PAS FIXE : −24,2 % dans un cas, +8,4 % dans
 l'autre. Aucun controle de vraisemblance portant sur le NIVEAU du Best
 Estimate ne pouvait donc l'attraper — c'est ce qui rend ce defaut
 particulierement discret.

 ⚠️ L'ASYMETRIE AVEC LE VOISIN EST LE REVELATEUR.
 `deriver_charges_depuis_provisions`, dix fonctions plus haut, ecrit
 explicitement que « les provisions sont alignees sur l'ANNEE REELLE, jamais
 positionnellement : un decalage produirait des charges silencieusement
 fausses ». La meme exigence n'etait pas tenue pour les primes.

 ⚠️ ET UN QUATRIEME MAILLON, QUE LES DEUX AUDITS NE TRACENT PAS : `annee_debut`,
 declare par l'appelant, n'atteignait QUE le diagnostic. La construction ne le
 recevait pas, si bien que `annee_min` restait None des que la source etait une
 MATRICE — le cas courant. Meme en rendant la table, rien n'aurait pu la
 rattacher.

 ⚠️ CE QUI RESTE, ET C'EST NORMAL : une annee reellement sans prime garde un
 effet sur BF et Cape Cod (−3,2 % ici). Ce n'est pas un decalage, c'est
 l'absence d'exposition sur cette annee-la, et elle est NOMMEE.
=============================================================================
"""

import unittest

import numpy as np
import pandas as pd

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    RAA)

AN0 = 1981                      # RAA : 1981..1990
PRIMES = [28000., 25000., 32000., 37000., 36000.,
          40000., 42000., 45000., 47000., 50000.]


def _table(annees, valeurs):
    return pd.DataFrame({'annee_survenance': list(annees),
                         'prime': list(valeurs)})


def _run(table):
    return AgentA7Provisionnement(verbose=False).run(
        source=np.asarray(RAA, dtype=float), mode_declare='cumule',
        primes=table, annee_debut=AN0, generer_graphiques=False,
        generer_word=False, generer_html=False, n_sim_bootstrap=30, seed=42)


class _Socle(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        n = len(PRIMES)
        cls.complet = _run(_table(range(AN0, AN0 + n), PRIMES))
        cls.trou = _run(_table(
            [a for a in range(AN0, AN0 + n) if a != 1985],
            [v for a, v in zip(range(AN0, AN0 + n), PRIMES) if a != 1985]))
        cls.tot = _run(_table(range(1979, AN0 + n), [20000., 24000.] + PRIMES))

    @staticmethod
    def _al(r):
        return ' '.join(str(a) for a in (r['n1'].get('alertes') or []))


# =============================================================================
#  T1 — UNE TABLE QUI COMMENCE PLUS TOT NE DECALE PLUS RIEN
# =============================================================================

class T1_Aucun_Decalage_Silencieux(_Socle):

    def test_les_annees_hors_perimetre_sont_ignorees_et_dites(self):
        be_ref = float(self.complet['n4']['best_estimate'])
        be_tot = float(self.tot['n4']['best_estimate'])
        self.assertAlmostEqual(
            be_tot, be_ref, delta=1.0,
            msg="une table commencant deux ans plus tot deplace le Best "
                "Estimate de %s a %s : l'exposition est encore rattachee a sa "
                "POSITION, pas a son annee." % (be_ref, be_tot))
        self.assertIn(
            'hors du périmètre', self._al(self.tot),
            "les annees hors triangle sont ecartees SANS LE DIRE")
        print('    OK L10-1 table 1979+ : BE identique a la reference (%s), '
              'annees hors perimetre nommees' % round(be_ref))

    def test_les_methodes_a_exposition_sont_elles_aussi_identiques(self):
        """⚠️ LE BE PEUT MASQUER : il est une moyenne ponderee. BF et Cape Cod
        sont les methodes qui CONSOMMENT l'exposition — c'est chez elles que le
        decalage se voyait le plus (−27,8 % et +24,8 % mesures)."""
        for cle in ('bf', 'cape_cod'):
            a = float((self.complet['n3'].get(cle) or {}).get('reserve_totale') or 0)
            b = float((self.tot['n3'].get(cle) or {}).get('reserve_totale') or 0)
            self.assertAlmostEqual(
                b, a, delta=max(1.0, a * 0.001),
                msg='%s : %s contre %s' % (cle, b, a))
        print('    OK L10-2 BF et Cape Cod identiques a la reference')


# =============================================================================
#  T2 — UNE ANNEE MANQUANTE EST NOMMEE, ET SEULE ELLE EST TOUCHEE
# =============================================================================

class T2_Une_Annee_Manquante_Est_Nommee(_Socle):

    def test_l_alerte_nomme_l_annee_au_lieu_de_parler_de_longueur(self):
        al = self._al(self.trou)
        self.assertIn(
            '1985', al,
            "l'alerte ne nomme pas l'annee manquante : elle parlait de "
            "« vecteur plus court », ce qui fait croire que seule la DERNIERE "
            "annee est touchee.")
        self.assertNotIn(
            'plus court', al,
            "l'ancienne alerte trompeuse est revenue")
        print('    OK L10-3 alerte : %s' % al[:120])

    def test_le_decalage_a_disparu_meme_si_l_effet_reel_demeure(self):
        """⚠️ CE QUI RESTE EST LE VRAI EFFET. 1985 n'a pas de prime : BF et
        Cape Cod n'ont pas d'exposition sur cette annee-la. Ce n'est pas un
        decalage. Mais l'ecart doit etre PETIT devant celui du decalage."""
        be_ref = float(self.complet['n4']['best_estimate'])
        be_trou = float(self.trou['n4']['best_estimate'])
        ecart = abs(be_trou / be_ref - 1) * 100
        self.assertLess(
            ecart, 10.0,
            'ecart de %.1f %% : une seule annee sans prime ne peut pas '
            'deplacer le BE a ce point — le decalage est revenu.' % ecart)
        self.assertGreater(
            ecart, 0.0,
            "aucun effet du tout : l'annee manquante devrait retirer son "
            "exposition a BF et Cape Cod")
        print('    OK L10-4 trou en 1985 : ecart %.1f %% (le decalage valait '
              '24,2 %%)' % ecart)


# =============================================================================
#  T3 — SANS AXE D'ANNEES CONNU, ON REFUSE PLUTOT QUE DE DECALER
# =============================================================================

class T3_Sans_Repere_On_Refuse(unittest.TestCase):

    def test_une_table_sans_annee_min_connue_est_ignoree_et_dite(self):
        """⚠️ MIEUX VAUT AUCUNE EXPOSITION QU'UNE EXPOSITION DECALEE."""
        n = len(PRIMES)
        r = AgentA7Provisionnement(verbose=False).run(
            source=np.asarray(RAA, dtype=float), mode_declare='cumule',
            primes=_table(range(AN0, AN0 + n), PRIMES),
            generer_graphiques=False, generer_word=False, generer_html=False,
            n_sim_bootstrap=30, seed=42)          # PAS d'annee_debut
        al = ' '.join(str(a) for a in (r['n1'].get('alertes') or []))
        self.assertIn(
            "axe d'années", al,
            "sans repere, la table est rattachee quand meme : c'est le "
            "decalage silencieux qui revient.")
        print('    OK L10-5 sans axe declare : primes ignorees et dites')

    def test_un_vecteur_nu_conserve_le_comportement_historique(self):
        """⚠️ LA CONTRE-EPREUVE. Un vecteur n'a pas d'axe : on ne peut que le
        tronquer ou le completer. Ce chemin ne doit pas avoir change."""
        r = AgentA7Provisionnement(verbose=False).run(
            source=np.asarray(RAA, dtype=float), mode_declare='cumule',
            primes=np.array(PRIMES), annee_debut=AN0,
            generer_graphiques=False, generer_word=False, generer_html=False,
            n_sim_bootstrap=30, seed=42)
        self.assertTrue(r.get('success'), r.get('erreur'))
        self.assertGreater(
            float((r['n3'].get('bf') or {}).get('reserve_totale') or 0), 0,
            'un vecteur nu ne produit plus de Bornhuetter-Ferguson')
        print('    OK L10-6 vecteur nu : chemin historique intact, BF = %s'
              % round(float(r['n3']['bf']['reserve_totale'])))


if __name__ == '__main__':
    unittest.main(verbosity=2)
