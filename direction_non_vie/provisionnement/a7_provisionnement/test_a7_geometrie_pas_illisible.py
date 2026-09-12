# -*- coding: utf-8 -*-
"""UN PAS QU'ON NE SAIT PAS LIRE NE SE REMPLACE PAS PAR « 1 ».

⚠️⚠️ CE SCEAU MANQUAIT, ET C'EST MESURE. Le correctif qui ferme le retour
anticipe `m <= n` de `analyser_geometrie` est arrive SANS garde-fou : plant du
12/09/2026 sur l'arbre corrige — le retour anticipe remis en entier —
`test_a7_geometrie` et `test_a7_couture_ingestion` rendent « Ran 22 tests /
OK », et `test_a7_geometrie_deux_portes` (qui garde l'AUTRE trou de la meme
zone, celui de `_cumuler_et_masquer`) rend « Ran 3 tests / OK ». Rien ne
mordait.

DEUX TROUS VOISINS, ET UN SEUL ETAIT GARDE. Ils vivent tous deux dans la
lecture du pas de developpement, et aucun ne couvre l'autre :

  · `_cumuler_et_masquer` repondait « pas = 1 » a « je ne sais pas » (le
    `or 1`) — garde par `test_a7_geometrie_deux_portes` ;
  · `analyser_geometrie` rendait `pas = 1, transforme=False` SANS MEME
    consulter `pas_de_developpement`, des que `m <= n` — c'est CE fichier.

LE CAS, ET IL EST ORDINAIRE. Huit annees de survenance ANNUELLES, un
developpement TRIMESTRIEL, l'assureur ne fournissant que les huit premiers
trimestres : la ligne i a ete observee 4*(8-i) trimestres, tronques a huit
colonnes. Donc m = 8 = n, et le retour anticipe mordait.

MESURE DU 12/09/2026, sur l'arbre NON corrige :
    longueurs observees      [8, 8, 8, 8, 8, 8, 8, 4]
    pas_de_developpement(C)  None      <- le module dit qu'il ne sait pas
    la porte rendait         pas=1, transforme=False, AUCUNE info
    24 des 60 cellules OBSERVEES (40 %) tombaient hors de la frontiere
        i+j<n : les multiplier par DIX ne deplacait pas un centime
    reserve vraie (ultimes connus par construction)   2 917 604,44 EUR
    Best Estimate publie                              3 703 869,00 EUR
    ecart  +26,9 %, statut AMBRE, aucune alerte de geometrie

⚠️ L'ECART N'EST PAS UNE CONSTANTE, ET CE SCEAU NE L'EPINGLE PAS. Le premier
auditeur mesure -48,2 % sur SA cadence, moi +26,9 % sur la mienne : le signe
et l'ampleur dependent du profil d'ecoulement. Ce qui ne depend de rien, et
c'est ce qu'on verrouille ici, est que des cellules RENSEIGNEES ne soient pas
ecartees en silence.

⚠️ CE QUE CE SCEAU NE DIT PAS. Il ne prescrit pas le TRAITEMENT — refuser ou
agreger releve du correctif, pas du garde-fou. Il exige seulement que le
module ne PUBLIE PAS un dossier dont il aurait ecarte des paiements fournis
sans le dire.
"""
import logging
import unittest
import warnings

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement)
from direction_non_vie.provisionnement.a7_provisionnement.geometrie_triangle import (
    GeometrieRefusee, analyser_geometrie, longueurs_observees,
    pas_de_developpement)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, RAA)

#: ⚠️⚠️ ON NE COUPE PAS LES JOURNAUX A L'IMPORT. `core/test_journaux_
#: importables.py::F5_LeDepotEntier` l'interdit pour tout le depot, et
#: `test_a7_ibrahim` l.347 rappelle pourquoi : un `logging.disable(CRITICAL)`
#: de script de verification a deja MASQUE un `logger.error` reel et laisse
#: une regression survivre DEUX lots. La sourdine est donc bornee a la classe.
_SOURDINE = None


def _triangle_infra_annuel(n=8, pas=4, colonnes=8, croissance=1.03):
    """n annees ANNUELLES, developpement au pas `pas`, tronque a `colonnes`.

    Les ultimes sont FIXES : la reserve vraie n'est donc pas une estimation,
    c'est une soustraction.
    """
    q = np.arange(pas * n)
    part = 1.0 - 0.86 ** (q + 1)
    part = part / part[-1]
    ultimes = np.array([1_000_000.0 * croissance ** i for i in range(n)])
    C = np.zeros((n, colonnes))
    for i in range(n):
        vus = min(pas * (n - i), colonnes)
        for j in range(vus):
            C[i, j] = ultimes[i] * part[j]
    vraie = sum(ultimes[i] - C[i, min(pas * (n - i), colonnes) - 1]
                for i in range(n))
    return C, float(vraie)


def _run(C, **kw):
    a = dict(source=np.asarray(C, dtype=float), mode_declare='cumule',
             arrete='31/12/2026', ref_client='GEO3',
             generer_graphiques=False, generer_word=False,
             generer_html=False, n_sim_bootstrap=0, seed=42)
    a.update(kw)
    return AgentA7Provisionnement(verbose=False).run(**a)


class T_Un_Pas_Illisible_Ne_Devient_Pas_Un(unittest.TestCase):
    """Le cas exclu par `m <= n`, et la contre-epreuve qui le borne."""

    @classmethod
    def setUpClass(cls):
        global _SOURDINE
        _SOURDINE = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        warnings.filterwarnings('ignore')

    @classmethod
    def tearDownClass(cls):
        logging.disable(_SOURDINE)

    def test_GEO4_1_le_module_reconnait_ne_pas_savoir_lire_le_pas(self):
        """LA PREMISSE DU SCEAU, MESUREE PLUTOT QUE SUPPOSEE.

        Si `pas_de_developpement` savait lire ce triangle, il n'y aurait rien
        a garder : le controle porterait sur un chemin jamais emprunte.
        """
        C, _vraie = _triangle_infra_annuel()
        self.assertEqual(C.shape, (8, 8), 'la forme du cas a change')
        self.assertEqual(
            list(longueurs_observees(C)), [8, 8, 8, 8, 8, 8, 8, 4],
            'le profil de longueurs n est plus celui qui declenche le defaut')
        self.assertIsNone(
            pas_de_developpement(C),
            'le module sait desormais lire ce pas : ce sceau ne prouve plus '
            'ce qu il croit prouver, il faut le reconstruire')
        print('    OK GEO4-1 : longueurs %s, pas lu = None'
              % list(longueurs_observees(C)))

    def test_GEO4_2_la_porte_ne_publie_pas_un_pas_de_1_en_silence(self):
        """⚠️ LE CRITERE EST LA DONNEE, PAS LA FORME. Soit la porte REFUSE,
        soit elle TRANSFORME et le DIT — mais elle ne peut pas rendre
        « pas = 1, rien a signaler » sur un triangle dont elle vient de dire
        qu'elle ne sait pas lire le pas."""
        C, _vraie = _triangle_infra_annuel()
        try:
            geo = analyser_geometrie(C)
        except GeometrieRefusee as refus:
            self.assertIn(
                'cellule', str(refus).lower(),
                'le refus ne nomme pas les cellules observees en cause')
            print('    OK GEO4-2 : refuse, et le motif nomme les cellules')
            return
        self.assertTrue(
            geo.get('transforme') or geo.get('infos'),
            'la porte a rendu pas=%s, transforme=%s et %d info(s) : elle '
            'affirme un pas que la donnee contredit'
            % (geo.get('pas'), geo.get('transforme'), len(geo.get('infos') or [])))
        print('    OK GEO4-2 : transforme et declare (pas=%s, %d info)'
              % (geo.get('pas'), len(geo.get('infos') or [])))

    def test_GEO4_3_aucun_paiement_fourni_n_est_ecarte_sans_le_dire(self):
        """LA PROPRIETE QUI COMPTE, ET ELLE NE DEPEND D'AUCUN MONTANT.

        On multiplie par DIX les seules cellules qui tombent hors de la
        frontiere `i+j<n`. Si le dossier est publie ET que le Best Estimate
        ne bouge pas, c'est la preuve que personne ne les lit.
        """
        C, _vraie = _triangle_infra_annuel()
        n, m = C.shape
        muettes = [(i, j) for i in range(n) for j in range(m)
                   if C[i, j] != 0.0 and j > min(n - 1 - i, m - 1)]
        self.assertTrue(
            muettes,
            'aucune cellule hors frontiere : le cas ne pose plus la question')

        base = _run(C)
        if not base.get('success'):
            print('    OK GEO4-3 : le dossier est refuse — %d cellule(s) '
                  'hors frontiere, aucune n est publiee en silence'
                  % len(muettes))
            return

        C10 = C.copy()
        for (i, j) in muettes:
            C10[i, j] *= 10.0
        autre = _run(C10)
        be_a = (base.get('n4') or {}).get('best_estimate')
        be_b = (autre.get('n4') or {}).get('best_estimate')
        self.assertNotEqual(
            be_a, be_b,
            'le dossier est PUBLIE (BE = %s) et multiplier par dix les %d '
            'cellule(s) observees hors frontiere ne deplace pas un centime : '
            'elles sont ecartees en silence' % (be_a, len(muettes)))
        print('    OK GEO4-3 : %d cellule(s) hors frontiere, et elles pesent'
              % len(muettes))

    def test_GEO4_4_les_dossiers_ordinaires_ne_bougent_pas(self):
        """LA CONTRE-EPREUVE. Un sceau qui refuse tout ne garde rien : les
        quatre montants de reference du depot doivent traverser intacts."""
        attendus = {
            'GenIns': (np.asarray(GENINS, dtype=float), 18_680_856.0),
            'RAA': (np.asarray(RAA, dtype=float), 52_135.0),
            'GenIns tronque 10x6': (np.asarray(GENINS, dtype=float)[:, :6],
                                    14_760_181.0),
            'RAA tronque 10x7': (np.asarray(RAA, dtype=float)[:, :7],
                                 53_816.0),
        }
        for nom, (C, attendu) in attendus.items():
            with self.subTest(dossier=nom):
                r = _run(C)
                self.assertTrue(r.get('success'),
                                '%s est refuse : le sceau mord trop large '
                                '(%s)' % (nom, r.get('erreur')))
                be = (r.get('n4') or {}).get('best_estimate')
                self.assertAlmostEqual(
                    float(be), attendu, places=0,
                    msg='%s : %s au lieu de %s' % (nom, be, attendu))
        print('    OK GEO4-4 : les 4 dossiers de reference sont au centime')


if __name__ == '__main__':
    unittest.main(verbosity=2)
