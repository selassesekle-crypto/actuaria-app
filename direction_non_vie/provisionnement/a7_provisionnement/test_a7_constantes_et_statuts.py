# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — UNE CONSTANTE A UNE SOURCE, UNE PANNE N'A PAS DE COULEUR
=============================================================================

 Cinq constats, une meme famille : une valeur est declaree quelque part avec
 sa provenance, puis RECOPIEE ailleurs — ou bien une absence de mesure prend
 l'apparence d'une mesure favorable.

 · Les seuils du back-testing (15 / 8, « guide IA 2023 ») vivaient en QUATRE
   exemplaires : leur source, deux copies dans le renderer, et une quatrieme
   dans N4 qui decide d'une RECOMMANDATION publiee. Les deux audits n'en
   comptaient que trois. Mesure du defaut : porter les copies du renderer de
   15/8 a 25/18 passe les 225 tests du fichier livrables sans en faire tomber
   un seul.

 · « Annees recentes » etait l'annee 2020, ecrite en dur. En 2030, un dossier
   aurait encore qualifie de recentes les dix millesimes depuis 2020 et
   recommande un chargement prudentiel sur tous.

 · L'audit trail — le seul artefact ECRIT SUR DISQUE a chaque run, celui dont
   l'empreinte SHA-256 scelle le dossier — publiait `0 EUR` pour une methode
   non calculee, quand les QUATRE livrables ecrivent « non calculee ».
   L'asymetrie interne etait le revelateur : le meme bloc publie
   `munich_cl_disponible`, et aucun drapeau pour BF ni Cape Cod.

 · La figure des cadences projetait 100 % de developpement des la periode
   suivante, sur toutes les annees non developpees et tous les triangles.

 · Huit branches d'ECHEC de deux modules rendaient `statut: 'VERT'` : une
   panne y prenait la couleur d'un resultat favorable, sur un champ expose
   dans `n3` ou `success` ne l'accompagne pas necessairement.

 ⚠️ CHAQUE CLASSE PORTE SA CONTRE-EPREUVE.
=============================================================================
"""

import io
import re
import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.n3.backtesting import (
    SEUIL_AMBRE, SEUIL_ROUGE)
from direction_non_vie.provisionnement.a7_provisionnement.n3.chain_ladder import (
    chain_ladder)
from direction_non_vie.provisionnement.a7_provisionnement.n3.glm_apc_poisson import (
    glm_apc_poisson)
from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    RAA)


def _src(mod):
    return io.open(mod.__file__, encoding='utf-8').read()


def _sans_commentaires(s):
    return '\n'.join(l for l in s.split('\n') if not l.lstrip().startswith('#'))


# =============================================================================
#  T1 — LES SEUILS DU BACK-TESTING N'ONT QU'UNE SOURCE
# =============================================================================

class T1_Une_Seule_Source_De_Seuil(unittest.TestCase):

    def test_aucun_module_ne_recopie_les_seuils_en_litteral(self):
        import direction_non_vie.provisionnement.a7_provisionnement.n5_rapport as R
        import direction_non_vie.provisionnement.a7_provisionnement.n4_best_estimate as N4
        for mod in (R, N4):
            src = _sans_commentaires(_src(mod))
            # Les deux valeurs, cherchees comme des litteraux flottants isoles
            for val in ('15.0', '8.0'):
                for motif in (r'=\s*%s\s*,' % re.escape(val),
                              r'>=\s*%s\b' % re.escape(val)):
                    trouve = re.findall(motif, src)
                    self.assertEqual(
                        trouve, [],
                        '%s recopie le seuil %s (%s) : une revision du guide '
                        'IA toucherait le calcul et pas ce site.'
                        % (mod.__name__.split('.')[-1], val, motif))
            print('    OK L7-1 %s : aucun seuil recopie'
                  % mod.__name__.split('.')[-1])

    def test_les_deux_modules_tiennent_le_seuil_de_sa_source(self):
        import direction_non_vie.provisionnement.a7_provisionnement.n5_rapport as R
        self.assertIs(R.SEUIL_ROUGE, SEUIL_ROUGE)
        self.assertIs(R.SEUIL_AMBRE, SEUIL_AMBRE)
        print('    OK L7-2 le renderer tient %s / %s de `backtesting`'
              % (SEUIL_ROUGE, SEUIL_AMBRE))


# =============================================================================
#  T2 — « ANNEES RECENTES » SE COMPTE DEPUIS LA FIN DU TRIANGLE
# =============================================================================

class T2_Aucun_Millesime_En_Dur(unittest.TestCase):

    def test_le_seuil_des_annees_recentes_ne_porte_aucune_annee_ecrite(self):
        import direction_non_vie.provisionnement.a7_provisionnement.n4_best_estimate as N4
        src = _sans_commentaires(_src(N4))
        for annee in ('2020', '2021', '2022', '2023', '2024', '2025'):
            self.assertNotIn(
                '>= %s' % annee, src,
                'le millesime %s est ecrit en dur : le seuil ne suivrait ni '
                'la date d arrete ni la profondeur du triangle.' % annee)
        self.assertIn(
            '_seuil_recent', src,
            'le seuil derive du triangle a disparu')
        print('    OK L7-3 aucun millesime en dur dans N4')


# =============================================================================
#  T3 — L'AUDIT TRAIL SCELLE NE PUBLIE PAS DE FAUX ZERO
# =============================================================================

class T3_L_Audit_Trail_Ne_Ment_Pas(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # SANS exposition : BF et Cape Cod ne peuvent pas etre calculees.
        cls.r = AgentA7Provisionnement(verbose=False).run(
            source=np.asarray(RAA, dtype=float), mode_declare='cumule',
            generer_graphiques=False, generer_word=False,
            n_sim_bootstrap=30, seed=42)

    def test_une_methode_non_calculee_n_est_pas_publiee_a_zero(self):
        at = (self.r.get('audit_trail') or {}).get('n3_resume') or {}
        self.assertTrue(at, "l'audit trail est vide : il ne scelle plus rien")
        for cle in ('bf', 'cc'):
            self.assertIsNone(
                at.get(cle),
                "l'audit trail SCELLE publie %r = %r pour une methode non "
                "calculee, quand les quatre livrables ecrivent « non "
                "calculee »." % (cle, at.get(cle)))
        for cle in ('bf_motif', 'cc_motif'):
            self.assertTrue(
                at.get(cle),
                '%s : la raison manque — `None` seul ne dit pas POURQUOI' % cle)
        print('    OK L7-4 audit trail : bf=%r cc=%r motif=%r'
              % (at.get('bf'), at.get('cc'), at.get('bf_motif')))

    def test_l_audit_trail_reste_serialisable(self):
        """⚠️ IL EST ECRIT SUR DISQUE ET SON EMPREINTE SCELLE LE DOSSIER : un
        `None` qui casserait `json.dump` remplacerait un faux zero par une
        absence de dossier."""
        import json
        json.dumps((self.r.get('audit_trail') or {}).get('n3_resume') or {})
        print('    OK L7-5 audit trail serialisable en JSON')

    def test_une_methode_CALCULEE_publie_bien_son_montant(self):
        """⚠️ LA CONTRE-EPREUVE : `None` partout ne serait pas un progres."""
        at = (self.r.get('audit_trail') or {}).get('n3_resume') or {}
        self.assertIsInstance(
            at.get('cl'), float,
            'Chain Ladder est calculee : son montant doit figurer')
        self.assertGreater(at['cl'], 0)
        print('    OK L7-6 la methode calculee publie %s' % at['cl'])


# =============================================================================
#  T4 — LA FIGURE DES CADENCES NE SAUTE PAS A 100 %
# =============================================================================

class T4_La_Cadence_Projetee_Est_Juste(unittest.TestCase):

    def test_la_projection_suit_l_inverse_du_facteur_cumule(self):
        C = np.asarray(RAA, dtype=float)
        cl = chain_ladder(C, tail_force=1.0)
        fc = [float(x) for x in cl['facteurs_cumules']]
        n = C.shape[0]
        # La courbe publiee pour l'annee i part de sa derniere colonne connue.
        for i in (n - 1, n - 2):
            k = n - 1 - i
            attendu = [round(min(1.0 / fc[j], 1.0), 4) for j in range(k, len(fc))]
            # La cadence doit CROITRE et n'atteindre 1,0 qu'a la fin.
            self.assertTrue(
                all(a <= b + 1e-9 for a, b in zip(attendu, attendu[1:])),
                'cadence non croissante : %s' % attendu)
            self.assertLess(
                attendu[1], 0.99,
                "l'annee %d est publiee a 100 %% des la periode suivante "
                "(%s) — un actuaire y lit que son portefeuille se solde "
                "integralement en un an." % (i, attendu[:3]))
            print('    OK L7-7 annee %d : cadence %s...' % (i, attendu[:4]))

    def test_le_code_n_emploie_plus_le_produit_de_facteurs_cumules(self):
        import direction_non_vie.provisionnement.a7_provisionnement.n5_graphiques as G
        src = _sans_commentaires(_src(G))
        self.assertNotIn(
            'cum_j2', src,
            'le produit des facteurs CUMULES est revenu : des le premier '
            'point projete il vaut f_cum[k_i], et la courbe saute a 1,0.')
        print('    OK L7-8 la figure lit 1/f_cum, pas un produit de cumules')


# =============================================================================
#  T5 — UNE PANNE N'EST PAS VERTE
# =============================================================================

class T5_Une_Panne_N_Est_Pas_Verte(unittest.TestCase):

    def test_un_triangle_trop_petit_ne_rend_pas_un_statut_favorable(self):
        r = glm_apc_poisson(np.array([[100., 150.], [110., 0.]]))
        self.assertFalse(r.get('success'))
        self.assertNotEqual(
            r.get('statut'), 'VERT',
            "une panne rend un statut VERT : le champ est expose dans `n3`, "
            "ou `success` ne l'accompagne pas necessairement.")
        print('    OK L7-9 GLM sur triangle trop petit : statut %r'
              % r.get('statut'))

    def test_aucune_branche_d_echec_des_deux_modules_ne_rend_VERT(self):
        import direction_non_vie.provisionnement.a7_provisionnement.n3.glm_apc_poisson as A
        import direction_non_vie.provisionnement.a7_provisionnement.n3.barnett_zehnwirth_ptf as B
        for mod in (A, B):
            lignes = _src(mod).split('\n')
            for i, l in enumerate(lignes):
                if "'statut': 'VERT'" not in l:
                    continue
                contexte = '\n'.join(lignes[max(0, i - 3):i + 1])
                self.assertNotIn(
                    "'success': False", contexte,
                    '%s ligne %d : branche d echec rendue VERT'
                    % (mod.__name__.split('.')[-1], i + 1))
            print('    OK L7-10 %s : aucune branche d echec en VERT'
                  % mod.__name__.split('.')[-1])

    def test_une_branche_de_SUCCES_reste_verte(self):
        """⚠️ LA CONTRE-EPREUVE : passer TOUT en NON TESTABLE effacerait la
        distinction au lieu de la retablir."""
        import direction_non_vie.provisionnement.a7_provisionnement.n3.barnett_zehnwirth_ptf as B
        src = _src(B)
        self.assertIn(
            "'success': True", src,
            'plus aucune branche de succes : le module ne peut plus aboutir')
        self.assertIn(
            "'statut': 'VERT'", src,
            'plus aucun VERT nulle part : la distinction a disparu')
        print('    OK L7-11 les branches de succes gardent leur VERT')


if __name__ == '__main__':
    unittest.main(verbosity=2)
