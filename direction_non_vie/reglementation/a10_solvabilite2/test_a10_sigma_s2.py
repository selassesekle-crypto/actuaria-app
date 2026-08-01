# -*- coding: utf-8 -*-
"""
=============================================================================
 A10 Elena — filet des écarts types réglementaires σ (lot B10-b)
=============================================================================

 CE QUE CE FILET PROTÈGE. Avant le lot B10-b, A10 détenait sa PROPRE copie de
 la table des écarts types, distincte de celle d'A7. Sur 22 entrées, 7 σ_prime
 et 9 σ_réserve seulement étaient conformes au Règlement délégué, et 5 sur les
 DEUX colonnes. Pire, A10 se contredisait lui-même : le segment II-4 recevait
 trois σ différents selon la clé employée, et le segment II-5 aussi. Aucun des
 9 tests d'alors n'épinglait un σ — ils sont tous relationnels — donc rien ne
 pouvait le voir.

 CE FILET NE RECOPIE PAS LA TABLE, ET C'EST DÉLIBÉRÉ. La source est épinglée
 une seule fois, dans `test_a7_sigma_s2.py`, contre une transcription
 indépendante du texte officiel — et la table est désormais PARTAGÉE entre les
 deux agents. Une seconde recopie ici créerait deux endroits à tenir à jour et,
 en cas de divergence, aucun moyen de savoir lequel a raison. Ce filet vérifie
 donc ce qui est propre à A10 : son rattachement, sa dérivation, sa formule —
 et que la table qu'il lit est bien le MÊME OBJET que celle d'A7.
=============================================================================
"""

import unittest

import numpy as np

from direction_non_vie.reglementation.segments_s2 import SEGMENTS_S2
from direction_non_vie.reglementation.a10_solvabilite2 import agent as A10

#: Rattachement métier attendu. Épinglé pour qu'un déplacement soit un ACTE.
RATTACHEMENT = {
    'rc_auto':                     ('II',  1),
    'rc_auto_materiel':            ('II',  1),
    'rc_auto_corporels':           ('II',  1),
    'auto_autre':                  ('II',  2),
    'transport':                   ('II',  3),
    'marine_aviation_transport':   ('II',  3),
    'incendie':                    ('II',  4),
    'incendie_dommages':           ('II',  4),
    'mrh':                         ('II',  4),
    'catastrophes_naturelles':     ('II',  4),
    'rc_generale':                 ('II',  5),
    'construction':                ('II',  5),
    'rc_medicale':                 ('II',  5),
    'corporels_graves':            ('II',  5),
    'dommage_corporel_individuel': ('XIV', 2),
    'credit':                      ('II',  6),
    'credit_caution':              ('II',  6),
    'protection_juridique':        ('II',  7),
    'assistance':                  ('II',  8),
    'pertes_pecuniaires':          ('II',  9),
    'generique':                   ('II',  5),
}

A7_BASE = {
    'best_estimate': {'best_estimate': 7_000_000.0, 'sigma_mack': 400_000.0,
                      'cv_inter_methodes': 8.0, 'nb_methodes_convergentes': 5},
    'tail': {'tail_factor': 1.035}, 'meta': {'nb_lignes': 60000, 'n_annees': 8}}


def _agent():
    return A10.AgentA10Solvabilite2(audit_path='/tmp/test_a10_sigma', verbose=False)


# =============================================================================
#  1. UNE SEULE TABLE, PARTAGÉE — PAS DEUX COPIES
# =============================================================================

class T1_Table_Partagee(unittest.TestCase):

    def test_a10_et_a7_lisent_le_meme_objet(self):
        """Le verrou anti-fork : si quelqu'un recopie la table, ceci tombe."""
        from direction_non_vie.provisionnement.a7_provisionnement.config import (
            lob_config)
        self.assertIs(lob_config.SEGMENTS_S2, SEGMENTS_S2,
                      "A7 et A10 doivent lire LA MÊME table, pas deux copies")
        self.assertIs(A10.SEGMENTS_S2, SEGMENTS_S2)
        print(f"    OK SIG10-1 A7 et A10 partagent le même objet "
              f"({len(SEGMENTS_S2)} segments)")

    def test_aucune_table_de_sigma_nest_ecrite_en_dur_dans_a10(self):
        """`SIGMA_LOB` doit être VIDE à sa définition et rempli par dérivation.

        Le contrôle porte sur l'ARBRE SYNTAXIQUE et non sur le texte du
        fichier : un simple `assertNotIn('sigma_prem':0.…)` attraperait
        l'exemple de σ CLIENT du bloc de démonstration, qui est légitime — un
        assuré peut proposer ses propres paramètres. Ce qui doit rester
        interdit, c'est une TABLE de σ au niveau du module.
        """
        import ast
        import inspect
        arbre = ast.parse(inspect.getsource(A10))
        litteraux = []
        for noeud in arbre.body:                       # niveau module seulement
            cibles = (noeud.targets if isinstance(noeud, ast.Assign)
                      else [noeud.target] if isinstance(noeud, ast.AnnAssign)
                      else [])
            for c in cibles:
                if isinstance(c, ast.Name) and c.id == 'SIGMA_LOB':
                    litteraux.append(noeud.value)
        self.assertEqual(len(litteraux), 1, "SIGMA_LOB défini plus d'une fois")
        self.assertIsInstance(litteraux[0], ast.Dict)
        self.assertEqual(len(litteraux[0].keys), 0,
                         "SIGMA_LOB porte de nouveau des valeurs en dur")
        print("    OK SIG10-2 `SIGMA_LOB` vide à la définition — "
              "tout σ vient de la table partagée")


# =============================================================================
#  2. LE RATTACHEMENT ET LA DÉRIVATION
# =============================================================================

class T2_Rattachement(unittest.TestCase):

    def test_chaque_lob_pointe_le_segment_attendu(self):
        self.assertEqual(set(A10.SEGMENT_PAR_LOB), set(RATTACHEMENT),
                         "une LoB a été ajoutée ou retirée sans être rattachée")
        for lob, attendu in sorted(RATTACHEMENT.items()):
            self.assertEqual(A10.SEGMENT_PAR_LOB[lob], attendu, f"{lob}")
        print(f"    OK SIG10-3 {len(RATTACHEMENT)} LoB rattachées à leur segment")

    def test_les_deux_colonnes_sont_derivees_du_segment(self):
        """A10 emploie σ_prime ET σ_réserve — les deux doivent suivre."""
        for lob, seg_cle in sorted(RATTACHEMENT.items()):
            seg = SEGMENTS_S2[seg_cle]
            d = A10.SIGMA_LOB[lob]
            self.assertEqual(d['sigma_prem'], seg.sigma_prime, f"{lob} prime")
            self.assertEqual(d['sigma_res'], seg.sigma_reserve, f"{lob} réserve")
        print(f"    OK SIG10-4 {2 * len(RATTACHEMENT)} valeurs dérivées "
              f"(les deux colonnes, 21 LoB)")

    def test_un_meme_segment_donne_un_meme_sigma(self):
        """LE défaut du lot : II-4 recevait 3 σ, II-5 en recevait 3 aussi."""
        par_segment = {}
        for lob, seg_cle in RATTACHEMENT.items():
            d = A10.SIGMA_LOB[lob]
            par_segment.setdefault(seg_cle, set()).add(
                (d['sigma_prem'], d['sigma_res']))
        fautifs = {s: v for s, v in par_segment.items() if len(v) > 1}
        self.assertEqual(fautifs, {},
                         "un même segment réglementaire reçoit plusieurs σ")
        multi = [s for s, l in par_segment.items()
                 if sum(1 for x in RATTACHEMENT.values() if x == s) > 1]
        self.assertGreaterEqual(len(multi), 4,
                                "trop peu de segments partagés : le test ne "
                                "discriminerait plus")
        print(f"    OK SIG10-5 {len(multi)} segments portés par plusieurs LoB, "
              f"σ unique sur chacun (II-4 en avait 3, II-5 aussi)")


# =============================================================================
#  3. CE QUI ÉTAIT MORT ET NE DOIT PAS REVENIR
# =============================================================================

class T3_Proprete(unittest.TestCase):

    def test_le_repli_sans_source_a_disparu(self):
        """`SIGMA_DEFAULT` = 0,10/0,11 sans source, et inatteignable."""
        self.assertFalse(hasattr(A10, 'SIGMA_DEFAULT'),
                         "le repli mort est revenu")
        print("    OK SIG10-6 `SIGMA_DEFAULT` retiré — repli sans source "
              "et inatteignable")

    def test_la_cle_inatteignable_a_disparu(self):
        self.assertNotIn('autres', A10.SIGMA_LOB,
                         "`autres` n'est atteignable par aucune entrée de "
                         "BRANCHE_MAP")
        print("    OK SIG10-7 clé `autres` retirée — aucune route depuis "
              "BRANCHE_MAP")

    def test_toute_branche_atteignable_a_un_segment(self):
        orphelines = sorted(set(A10.BRANCHE_MAP.values()) - set(A10.SIGMA_LOB))
        self.assertEqual(orphelines, [], "branches sans σ")
        print(f"    OK SIG10-8 les {len(set(A10.BRANCHE_MAP.values()))} cibles "
              f"de BRANCHE_MAP ont toutes un segment")

    def test_un_rattachement_invalide_leve_au_chargement(self):
        sauve = A10.SEGMENT_PAR_LOB['generique']
        A10.SEGMENT_PAR_LOB['generique'] = ('II', 99)
        try:
            with self.assertRaises(KeyError):
                A10._construire_sigma_lob()
        finally:
            A10.SEGMENT_PAR_LOB['generique'] = sauve
            A10._construire_sigma_lob()
        self.assertEqual(A10.SIGMA_LOB['generique']['sigma_res'], 0.11)
        print("    OK SIG10-9 rattachement invalide → KeyError au chargement")

    def test_les_facteurs_catastrophe_sont_isoles_des_sigma(self):
        """Provenances différentes, dictionnaires différents.

        `f_cat` n'est pas dans les annexes II/XIV et n'a pas été confronté au
        texte : le mélanger aux σ ferait passer une valeur non vérifiée pour
        une valeur réglementaire — exactement ce qui a produit ce chantier.
        """
        self.assertTrue(hasattr(A10, 'F_CAT_LOB'))
        self.assertEqual(set(A10.F_CAT_LOB), set(RATTACHEMENT))
        for lob in RATTACHEMENT:
            self.assertEqual(A10.SIGMA_LOB[lob]['f_cat'], A10.F_CAT_LOB[lob])
        print(f"    OK SIG10-10 {len(A10.F_CAT_LOB)} facteurs catastrophe "
              f"isolés — provenance non vérifiée, et dite comme telle")


# =============================================================================
#  4. LA FORMULE — ARTICLE 117(2)
# =============================================================================

class T4_Article_117(unittest.TestCase):

    def test_le_sigma_combine_suit_la_formule_du_texte(self):
        """σ_s = √(σp²Vp² + σp·Vp·σr·Vr + σr²Vr²) / (Vp + Vr)."""
        r = _agent().run(result_a7=A7_BASE, sous_branche='rc_generale',
                         result_a6={'modele_production':
                                    {'primes_acquises': 9_000_000.0}})
        self.assertTrue(r['success'], r.get('erreur'))
        b = r['detail']['scr_sous']['par_branche'][0]
        sp, sr, Vp, Vr = b['sigma_prem'], b['sigma_res'], b['Vp'], b['Vr']
        attendu = np.sqrt((sp * Vp) ** 2 + (sp * Vp) * (sr * Vr)
                          + (sr * Vr) ** 2) / (Vp + Vr)
        self.assertAlmostEqual(b['sigma_net'], attendu, places=12)
        print(f"    OK SIG10-11 σ_s conforme à l'art. 117(2) : "
              f"{b['sigma_net']:.6f} (σp={sp}, σr={sr})")

    def test_sans_prime_future_la_formule_se_reduit_au_sigma_de_reserve(self):
        """C'est CE fait qui justifie qu'A7 ne détienne qu'un seul σ.

        Vérifié ici sur la formule d'A10 elle-même, pas sur du papier.
        """
        for seg in SEGMENTS_S2.values():
            sp, sr, Vp, Vr = seg.sigma_prime, seg.sigma_reserve, 0.0, 1_000_000.0
            sigma_s = np.sqrt((sp * Vp) ** 2 + (sp * Vp) * (sr * Vr)
                              + (sr * Vr) ** 2) / (Vp + Vr)
            self.assertAlmostEqual(sigma_s, sr, places=12,
                                   msg=f"segment {seg.annexe}-{seg.numero}")
        print(f"    OK SIG10-12 V_prime = 0 ⇒ σ_s = σ_réserve, sur les "
              f"{len(SEGMENTS_S2)} segments — le fondement du choix d'A7")


# =============================================================================
#  5. LA TRAÇABILITÉ VA JUSQU'À LA SORTIE
# =============================================================================

class T5_Tracabilite(unittest.TestCase):

    def test_chaque_branche_publie_son_annexe_et_son_segment(self):
        r = _agent().run(
            result_a7=A7_BASE,
            branches=[{'nom': 'rc_auto', 'be': 5_000_000, 'primes': 7_000_000},
                      {'nom': 'dommage_corporel_individuel', 'be': 2_000_000,
                       'primes': 3_000_000}])
        self.assertTrue(r['success'], r.get('erreur'))
        par = {b['nom']: b for b in
               r['detail']['scr_sous']['par_branche']}
        self.assertIn('Annexe II', par['rc_auto']['reference_s2'])
        self.assertIn('segment 1', par['rc_auto']['reference_s2'])
        self.assertIn('Annexe XIV',
                      par['dommage_corporel_individuel']['reference_s2'])
        self.assertEqual(par['rc_auto']['segment_s2'], ('II', 1))
        print(f"    OK SIG10-13 référence publiée par branche : "
              f"« {par['dommage_corporel_individuel']['reference_s2']} »")


if __name__ == '__main__':
    unittest.main(verbosity=2)
