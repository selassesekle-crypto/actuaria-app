# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 Ibrahim — filet des écarts types réglementaires σ (lot B10-a)
=============================================================================

 CE QUE CE FILET PROTÈGE, ET POURQUOI IL EXISTE. Avant le lot B10-a, quinze
 des dix-huit σ d'A7 étaient faux, tous commentés « Annexe II », deux citant
 un segment inexistant (« CAT naturelles », « Accidents corporels »), et la
 formule était attribuée à un article — le 105 du Règlement délégué — qui
 traite du risque de spread des captives. Rien ne pouvait le détecter :
 aucun test ne regardait ces valeurs.

 LA SOURCE, ET RIEN D'AUTRE. Les valeurs épinglées ici sont recopiées du
 Règlement délégué (UE) 2015/35, texte consolidé au 02.08.2022 — CELEX
 02015R0035-20220802, annexe II page 389 et annexe XIV page 430. Elles ne
 viennent NI du guide de l'Institut, NI d'A10, NI d'une table reconstruite.

 ⚠️ RECOPIE INDÉPENDANTE, ET C'EST VOLONTAIRE. Le tableau ci-dessous
 duplique `SEGMENTS_S2`. Un test qui importerait la table qu'il vérifie ne
 vérifierait rien : la duplication EST le mécanisme. Si les deux divergent un
 jour, c'est au texte officiel qu'il faut retourner, pas à l'autre copie.
=============================================================================
"""

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.config.lob_config import (
    LOB_CONFIG, SEGMENTS_S2, get_lob_config, get_segment_s2,
    get_sigma_eiopa, reference_s2)

# =============================================================================
#  LA SOURCE — recopiée à la main du texte consolidé, indépendamment du code
# =============================================================================

#: (annexe, numéro) -> (σ risque de primes, σ risque de réserve)
#: Annexe II p.389 — engagements non-vie, 12 segments.
#: Annexe XIV p.430 — engagements santé non-SLT, 4 segments.
SOURCE_OFFICIELLE = {
    ('II',  1): (0.10,  0.09),    # RC automobile
    ('II',  2): (0.08,  0.08),    # autre assurance des véhicules
    ('II',  3): (0.15,  0.11),    # maritime, aérienne et transport
    ('II',  4): (0.08,  0.10),    # incendie et autres dommages aux biens
    ('II',  5): (0.14,  0.11),    # RC générale
    ('II',  6): (0.19,  0.172),   # crédit et cautionnement
    ('II',  7): (0.083, 0.055),   # protection juridique
    ('II',  8): (0.064, 0.22),    # assistance
    ('II',  9): (0.13,  0.20),    # pertes pécuniaires diverses
    ('II', 10): (0.17,  0.20),    # réassurance accidents non proportionnelle
    ('II', 11): (0.17,  0.20),    # réassurance MAT non proportionnelle
    ('II', 12): (0.17,  0.20),    # réassurance dommages non proportionnelle
    ('XIV', 1): (0.05,  0.057),   # frais médicaux
    ('XIV', 2): (0.085, 0.14),    # protection du revenu
    ('XIV', 3): (0.096, 0.11),    # indemnisation des travailleurs
    ('XIV', 4): (0.17,  0.17),    # réassurance santé non proportionnelle
}

#: Rattachement métier de chaque LoB d'A7 à son segment officiel.
#: Épinglé ici pour qu'un déplacement soit un ACTE, pas un effet de bord.
RATTACHEMENT = {
    'rc_auto_materiel':            ('II',  1),
    'rc_auto_corporels':           ('II',  1),
    'mrh':                         ('II',  4),
    'rc_generale':                 ('II',  5),
    'rc_medicale':                 ('II',  5),
    'construction':                ('II',  5),
    'marine_aviation_transport':   ('II',  3),
    'transport':                   ('II',  3),
    'accidents_corporels':         ('XIV', 2),
    'dommage_corporel_individuel': ('XIV', 2),
    'generique':                   ('II',  5),
    'incendie_dommages':           ('II',  4),
    'protection_juridique':        ('II',  7),
    'catastrophes_naturelles':     ('II',  4),
    'credit_caution':              ('II',  6),
}


# =============================================================================
#  1. LA TABLE EST CELLE DU TEXTE
# =============================================================================

class T1_Table_Officielle(unittest.TestCase):

    def test_les_seize_segments_sont_presents_et_pas_un_de_plus(self):
        self.assertEqual(set(SEGMENTS_S2), set(SOURCE_OFFICIELLE),
                         "la table ne couvre pas exactement les annexes II et XIV")
        print(f"    OK SIG-1 {len(SEGMENTS_S2)} segments — annexe II (12) "
              f"et annexe XIV (4), ni plus ni moins")

    def test_chaque_sigma_vaut_celui_du_texte(self):
        for cle, (s_prem, s_res) in sorted(SOURCE_OFFICIELLE.items()):
            seg = SEGMENTS_S2[cle]
            self.assertAlmostEqual(seg.sigma_prime, s_prem, places=6,
                                   msg=f"{cle} : σ primes")
            self.assertAlmostEqual(seg.sigma_reserve, s_res, places=6,
                                   msg=f"{cle} : σ réserve")
        print(f"    OK SIG-2 32 valeurs (16 segments × 2 colonnes) conformes "
              f"au texte consolidé au 02.08.2022")

    def test_chaque_segment_porte_son_annexe_et_son_numero(self):
        """La provenance est dans la DONNÉE — c'est tout l'objet du lot."""
        for (annexe, numero), seg in SEGMENTS_S2.items():
            self.assertEqual(seg.annexe, annexe)
            self.assertEqual(seg.numero, numero)
            self.assertTrue(seg.libelle.strip(), f"{annexe}-{numero} sans libellé")
            self.assertTrue(seg.lignes_annexe_i.strip(),
                            f"{annexe}-{numero} sans lignes d'activité")
        print("    OK SIG-3 annexe, numéro, libellé et lignes d'activité "
              "portés par chaque segment")


# =============================================================================
#  2. LE TEST QUI A DISQUALIFIÉ UNE TABLE RECONSTRUITE
# =============================================================================

class T2_Signature_De_La_Source(unittest.TestCase):
    """Une table σ recopiée d'un tableur a une signature ; le texte n'en a pas.

    Une source non officielle proposée pendant l'investigation donnait
    σ_réserve = σ_prime − 0,01 sur onze lignes sur douze. Le texte, lui, n'a
    aucune régularité de ce genre — et c'est ce qui l'a écartée. Ces deux
    tests figent le critère, pour qu'une table reconstruite ne puisse pas
    entrer un jour sans se faire voir.
    """

    def test_aucune_relation_mecanique_entre_les_deux_colonnes(self):
        ecarts = {round(s.sigma_reserve - s.sigma_prime, 4)
                  for s in SEGMENTS_S2.values()}
        self.assertGreaterEqual(
            len(ecarts), 10,
            f"seulement {len(ecarts)} écarts distincts sur {len(SEGMENTS_S2)} "
            f"segments — signature d'une table reconstruite")
        print(f"    OK SIG-4 {len(ecarts)} écarts distincts sur "
              f"{len(SEGMENTS_S2)} segments — aucune relation mécanique")

    def test_la_reserve_depasse_la_prime_sur_une_majorite_de_segments(self):
        """Fait du texte, contre-intuitif, et impossible dans la table écartée."""
        sup = [f"{a}-{n}" for (a, n), s in SEGMENTS_S2.items()
               if s.sigma_reserve > s.sigma_prime]
        self.assertGreaterEqual(len(sup), 8,
                                "σ_réserve > σ_prime doit tenir sur au moins "
                                "8 segments (assistance : 6,4 % contre 22 %)")
        assist = SEGMENTS_S2[('II', 8)]
        self.assertAlmostEqual(assist.sigma_reserve - assist.sigma_prime,
                               0.156, places=6)
        print(f"    OK SIG-5 σ_réserve > σ_prime sur {len(sup)} segments ; "
              f"assistance +15,6 points")


# =============================================================================
#  3. LE RATTACHEMENT DES LoB, ET L'IMPOSSIBILITÉ DE DÉRIVER
# =============================================================================

class T3_Rattachement(unittest.TestCase):

    def test_chaque_lob_pointe_le_segment_attendu(self):
        self.assertEqual(set(LOB_CONFIG), set(RATTACHEMENT),
                         "une LoB a été ajoutée ou retirée sans être rattachée")
        for lob, attendu in sorted(RATTACHEMENT.items()):
            self.assertEqual(LOB_CONFIG[lob]['segment_s2'], attendu,
                             f"{lob} mal rattachée")
        print(f"    OK SIG-6 {len(RATTACHEMENT)} LoB rattachées à leur segment")

    def test_le_sigma_est_derive_de_la_table_jamais_saisi(self):
        """Le verrou anti-dérive : aucun σ n'est écrit à la main dans une LoB."""
        for lob, cfg in sorted(LOB_CONFIG.items()):
            attendu = SEGMENTS_S2[cfg['segment_s2']].sigma_reserve
            self.assertEqual(cfg['sigma_eiopa'], attendu, f"{lob} : σ divergent")
            self.assertEqual(get_sigma_eiopa(lob), attendu, f"{lob} : accesseur")
        print("    OK SIG-7 σ dérivé du segment pour les 15 LoB — "
              "les champs `lob_eiopa` et `sigma_eiopa` ne peuvent plus diverger")

    def test_le_champ_texte_qui_derivait_a_disparu(self):
        """`lob_eiopa` contredisait `sigma_eiopa` sur 3 LoB sur 15."""
        for lob, cfg in LOB_CONFIG.items():
            self.assertNotIn('lob_eiopa', cfg,
                             f"{lob} : le champ qui dérivait est revenu")
        print("    OK SIG-8 `lob_eiopa` retiré — un seul champ fait foi")

    def test_un_segment_inexistant_est_refuse_au_chargement(self):
        from direction_non_vie.provisionnement.a7_provisionnement.config import (
            lob_config as mod)
        sauve = LOB_CONFIG['generique']['segment_s2']
        LOB_CONFIG['generique']['segment_s2'] = ('II', 99)
        try:
            with self.assertRaises(KeyError):
                mod._appliquer_table_officielle()
        finally:
            LOB_CONFIG['generique']['segment_s2'] = sauve
            mod._appliquer_table_officielle()
        self.assertEqual(get_sigma_eiopa('generique'), 0.11)
        print("    OK SIG-9 un rattachement invalide lève au chargement, "
              "il ne peut pas atteindre un livrable")


# =============================================================================
#  4. C'EST BIEN LE σ DE RÉSERVE — art. 117(2) avec V_prime = 0
# =============================================================================

class T4_Colonne_Reserve(unittest.TestCase):

    def test_a7_emploie_la_colonne_reserve_et_non_la_colonne_primes(self):
        """Si quelqu'un intervertit les colonnes, ce test tombe."""
        differents = [lob for lob, cfg in LOB_CONFIG.items()
                      if SEGMENTS_S2[cfg['segment_s2']].sigma_prime
                      != SEGMENTS_S2[cfg['segment_s2']].sigma_reserve]
        self.assertGreaterEqual(
            len(differents), 8,
            "trop peu de LoB où les deux colonnes diffèrent — le test ne "
            "discriminerait plus")
        for lob in differents:
            seg = get_segment_s2(lob)
            self.assertEqual(get_sigma_eiopa(lob), seg.sigma_reserve)
            self.assertNotEqual(get_sigma_eiopa(lob), seg.sigma_prime)
        print(f"    OK SIG-10 colonne RÉSERVE employée sur les "
              f"{len(differents)} LoB où les deux colonnes diffèrent")

    def test_le_scr_vaut_trois_fois_sigma_reserve_fois_le_be(self):
        from direction_non_vie.provisionnement.a7_provisionnement.n4_best_estimate import (
            BestEstimateS2)
        moteur = BestEstimateS2()
        be = 10_000_000.0
        for lob in ('protection_juridique', 'credit_caution',
                    'accidents_corporels', 'catastrophes_naturelles'):
            r = moteur._calculer_scr(be, lob, get_lob_config(lob))
            attendu = 3.0 * get_segment_s2(lob).sigma_reserve * be
            self.assertAlmostEqual(r['scr_provisions'], round(attendu, 0),
                                   delta=1.0, msg=lob)
        print("    OK SIG-11 SCR = 3 × σ(réserve) × BE — art. 115, vérifié "
              "bout en bout sur 4 LoB")


# =============================================================================
#  5. LES DEUX CLÉS FANTÔMES, TRANCHÉES
# =============================================================================

class T5_Cles_Fantomes(unittest.TestCase):
    """Deux σ citaient un segment de l'annexe II qui n'existe pas."""

    def test_cat_nat_est_rattachee_a_incendie_et_non_a_un_segment_invente(self):
        seg = get_segment_s2('catastrophes_naturelles')
        self.assertEqual((seg.annexe, seg.numero), ('II', 4))
        self.assertAlmostEqual(get_sigma_eiopa('catastrophes_naturelles'), 0.10)
        self.assertNotAlmostEqual(get_sigma_eiopa('catastrophes_naturelles'),
                                  0.25, msg="l'ancien σ sans source est revenu")
        print("    OK SIG-12 cat-nat : σ 0,25 sans source → 0,10 (segment II-4) ; "
              "le module catastrophe (art. 119+) reste hors périmètre d'A7")

    def test_accidents_corporels_releve_de_la_sante_non_slt(self):
        for lob in ('accidents_corporels', 'dommage_corporel_individuel'):
            seg = get_segment_s2(lob)
            self.assertEqual((seg.annexe, seg.numero), ('XIV', 2), lob)
            self.assertAlmostEqual(get_sigma_eiopa(lob), 0.14, msg=lob)
        print("    OK SIG-13 accidents corporels : segment inventé → XIV-2 "
              "protection du revenu (0,085 → 0,14)")


# =============================================================================
#  6. LA TRAÇABILITÉ VA JUSQU'AU LIVRABLE
# =============================================================================

class T6_Tracabilite_Livrable(unittest.TestCase):
    """« Annexe II » était écrit EN DUR dans les rapports.

    Cela devient faux dès qu'une LoB relève de la santé non-SLT — ce qui est
    désormais le cas de deux d'entre elles.
    """

    def test_reference_s2_nomme_la_bonne_annexe(self):
        self.assertIn('Annexe XIV', reference_s2('accidents_corporels'))
        self.assertIn('segment 2',   reference_s2('accidents_corporels'))
        self.assertIn('Annexe II',   reference_s2('protection_juridique'))
        self.assertIn('segment 7',   reference_s2('protection_juridique'))
        print(f"    OK SIG-14 référence dynamique : "
              f"« {reference_s2('accidents_corporels')} »")

    def test_le_rapport_html_cite_lannexe_xiv_pour_une_lob_de_sante(self):
        from direction_non_vie.provisionnement.a7_provisionnement.agent import (
            AgentA7Provisionnement)
        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
            export_html)
        from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
            GENINS)
        r = AgentA7Provisionnement(verbose=False).run(
            source=np.asarray(GENINS, float), lob='accidents_corporels',
            mode_declare='cumule', generer_graphiques=False,
            generer_word=False, n_sim_bootstrap=100, seed=42)
        self.assertTrue(r['success'], r.get('erreur'))
        html = export_html(n1=r.get('n1', {}), n2=r['n2'], n3=r['n3'], n4=r['n4'])
        self.assertIn('Annexe XIV', html,
                      "le rapport doit citer l'annexe dont relève la LoB")
        self.assertIn('Art. 115', html,
                      "la formule doit être attribuée à l'article 115")
        self.assertNotIn('Art. 105', html,
                         "l'article 105 du Règlement délégué traite du risque "
                         "de spread des captives — il n'a rien à faire ici")
        taille = f"{len(html):,}".replace(',', ' ')
        print(f"    OK SIG-15 rapport HTML d'une LoB santé : « Annexe XIV » "
              f"présent, « Art. 105 » absent ({taille} octets)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
