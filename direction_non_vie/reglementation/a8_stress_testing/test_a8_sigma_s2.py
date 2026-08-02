# -*- coding: utf-8 -*-
"""
=============================================================================
 A8 Isabelle — filet des écarts types réglementaires σ (lot B10-c)
=============================================================================

 CE QUE CE FILET PROTÈGE. A8 détenait la TROISIÈME copie de la table des
 écarts types — après A7 et A10 — en double exemplaire à lui seul : six
 valeurs dans `data/marche/reference_actuaria.json` ET les mêmes six codées
 en dur dans le repli de `agent.py`. Une d'entre elles avait dérivé
 (`sigma_primes_rc_general` valait 0,11 au lieu de 0,14).

 MAIS LE VRAI DÉFAUT ÉTAIT AILLEURS, ET IL ÉTAIT PLUS GRAVE. Le σ n'était pas
 choisi par segment mais par recherche de sous-chaîne dans le nom de la
 branche, et se trompait sur 13 des 17 noms qu'A7 transmet — `'rc' in
 'rc_auto'` étant vrai, la RC automobile recevait le σ de la RC générale.
 Dix-sept branches ne produisaient que TROIS couples de σ ; elles en
 produisent sept.

 L'unique test d'alors n'épinglait ni σ ni SCR absolu, et il tournait sur
 `sous_branche='auto'` — la seule branche que l'aiguillage traitait bien.
=============================================================================
"""

import io
import json
import unittest
from pathlib import Path

import numpy as np

from direction_non_vie.reglementation.segments_s2 import SEGMENTS_S2
from direction_non_vie.reglementation.a8_stress_testing import agent as A8

#: Ce que chaque nom transmis par A7 doit obtenir. Épinglé : un déplacement
#: doit être un ACTE, pas un effet de bord d'une sous-chaîne.
ROUTAGE = {
    'auto':                        ('II',  1),
    'rc_auto':                     ('II',  1),
    'rc_auto_materiel':            ('II',  1),
    'rc_auto_corporels':           ('II',  1),
    'mrh':                         ('II',  4),
    'incendie_dommages':           ('II',  4),
    'catastrophes_naturelles':     ('II',  4),
    'rc_generale':                 ('II',  5),
    'rc_medicale':                 ('II',  5),
    'construction':                ('II',  5),
    'generique':                   ('II',  5),
    'marine_aviation_transport':   ('II',  3),
    'transport':                   ('II',  3),
    'credit_caution':              ('II',  6),
    'protection_juridique':        ('II',  7),
    'accidents_corporels':         ('XIV', 2),
    'dommage_corporel_individuel': ('XIV', 2),
}

#: Ce que l'ancien aiguillage par sous-chaîne donnait — conservé pour que la
#: correction reste lisible, et pour que la non-régression ait une cible.
ANCIEN_FAUX = {
    'rc_auto': ('II', 5), 'rc_auto_materiel': ('II', 5),
    'rc_auto_corporels': ('II', 5), 'mrh': ('II', 1),
    'catastrophes_naturelles': ('II', 1), 'construction': ('II', 1),
    'credit_caution': ('II', 1), 'protection_juridique': ('II', 1),
    'marine_aviation_transport': ('II', 1), 'transport': ('II', 1),
    'generique': ('II', 1), 'accidents_corporels': ('II', 5),
    'dommage_corporel_individuel': ('II', 5),
}

A7_SYNTH = {
    'success': True,
    'best_estimate': {'best_estimate': 2_914_930.0, 'sigma_mack': 45_000.0,
                      'cv_inter_methodes': 0.6, 'reserve_p75': 3_098_000.0,
                      'reserve_p90': 3_200_000.0},
    'bootstrap': {'p99_5': 3_640_000.0, 'p90': 3_200_000.0,
                  'p75': 3_098_000.0, 'p50': 2_900_000.0},
    'tail_factor': {'tail_factor': 1.037, 'methode_retenue': 'Clark'},
    'orsa_provisions': {'horizon_5ans': [3.0e6, 3.1e6, 3.2e6, 3.3e6, 3.4e6]},
    'chain_ladder': {'facteurs': [2.5, 1.8, 1.3, 1.1, 1.05]},
    'meta': {'nb_lignes': 70000, 'n_annees': 8},
}


def _segment_choisi(branche):
    """Reproduit la résolution d'A8, sans lancer l'agent."""
    cle = A8.BRANCHE_MAP.get(
        (branche or 'auto').lower().replace(' ', '_').replace('-', '_'),
        'generique')
    return A8.SEGMENT_PAR_LOB[cle]


def _run(branche):
    a7 = dict(A7_SYNTH); a7['sous_branche'] = branche
    return A8.AgentA8StressTesting(models_path='/tmp', audit_path='/tmp',
                                   verbose=False).run(
        result_a7=a7, fonds_propres=7_650_000.0, generer_graphiques=False)


# =============================================================================
#  1. PLUS AUCUNE COPIE — NI DANS LE JSON, NI DANS LE CODE
# =============================================================================

class T1_Plus_De_Copie(unittest.TestCase):

    CLES = ('sigma_primes_rc_auto', 'sigma_primes_incendie',
            'sigma_primes_rc_general', 'sigma_reserves_rc_auto',
            'sigma_reserves_incendie', 'sigma_reserves_rc_general')

    def test_le_json_ne_porte_plus_de_sigma(self):
        chemin = (Path(A8.__file__).resolve().parents[3]
                  / 'data' / 'marche' / 'reference_actuaria.json')
        self.assertTrue(chemin.is_file(), f"introuvable : {chemin}")
        bloc = json.load(io.open(chemin, encoding='utf-8'))[
            'parametres_scr_standard']['scr_souscription_non_vie']
        for cle in self.CLES:
            self.assertNotIn(cle, bloc, f"{cle} est revenu dans le JSON")
        self.assertIn('facteur_catastrophe_vent', bloc,
                      "les facteurs catastrophe, eux, doivent rester")
        print(f"    OK SIG8-1 les 6 sigma retires du JSON, "
              f"{len(bloc)} cles conservees")

    def test_le_repli_code_en_dur_ne_porte_plus_de_sigma(self):
        src = io.open(A8.__file__, encoding='utf-8').read()
        for cle in self.CLES:
            self.assertNotIn(f"'{cle}'", src,
                             f"{cle} est revenu en dur dans agent.py")
        print("    OK SIG8-2 les 6 sigma retires du repli code en dur")

    def test_a8_lit_la_table_partagee(self):
        """Le verrou anti-fork, comme pour A10."""
        from direction_non_vie.provisionnement.a7_provisionnement.config import (
            lob_config)
        self.assertIs(A8.SEGMENTS_S2, SEGMENTS_S2)
        self.assertIs(lob_config.SEGMENTS_S2, SEGMENTS_S2)
        print(f"    OK SIG8-3 A7, A10 et A8 partagent le meme objet "
              f"({len(SEGMENTS_S2)} segments)")


# =============================================================================
#  2. L'AIGUILLAGE — LE DÉFAUT PRINCIPAL DU LOT
# =============================================================================

class T2_Aiguillage(unittest.TestCase):

    def test_chaque_branche_obtient_son_segment(self):
        for branche, attendu in sorted(ROUTAGE.items()):
            self.assertEqual(_segment_choisi(branche), attendu,
                             f"branche '{branche}' mal aiguillee")
        print(f"    OK SIG8-4 {len(ROUTAGE)} branches aiguillees par SEGMENT")

    def test_les_treize_erreurs_de_sous_chaine_sont_corrigees(self):
        """Contre-épreuve : chacune obtenait autre chose, et ne l'obtient plus."""
        for branche, faux in sorted(ANCIEN_FAUX.items()):
            self.assertNotEqual(
                _segment_choisi(branche), faux,
                f"'{branche}' retombe sur l'ancien aiguillage {faux}")
        print(f"    OK SIG8-5 les {len(ANCIEN_FAUX)} branches mal aiguillees "
              f"ne le sont plus")

    def test_rc_auto_ne_recoit_plus_le_sigma_de_la_rc_generale(self):
        """`'rc' in 'rc_auto'` etait vrai — le piege le plus couteux."""
        for b in ('rc_auto', 'rc_auto_materiel', 'rc_auto_corporels'):
            seg = SEGMENTS_S2[_segment_choisi(b)]
            self.assertEqual((seg.annexe, seg.numero), ('II', 1), b)
            self.assertAlmostEqual(seg.sigma_prime, 0.10)
            self.assertAlmostEqual(seg.sigma_reserve, 0.09)
        rcg = SEGMENTS_S2[('II', 5)]
        self.assertNotAlmostEqual(rcg.sigma_prime, 0.10,
                                  msg="le test ne discrimine plus")
        print("    OK SIG8-6 RC auto -> II-1 (0,100/0,090) et non II-5")

    def test_la_mrh_ne_tombe_plus_dans_le_repli(self):
        """Le code testait `'mrd'`, qui n'est le nom de rien."""
        seg = SEGMENTS_S2[_segment_choisi('mrh')]
        self.assertEqual((seg.annexe, seg.numero), ('II', 4))
        print("    OK SIG8-7 MRH -> II-4 incendie (la faute de frappe `mrd` "
              "l'envoyait au repli)")

    def test_les_branches_de_sante_ne_vont_plus_en_rc_generale(self):
        for b in ('accidents_corporels', 'dommage_corporel_individuel'):
            seg = SEGMENTS_S2[_segment_choisi(b)]
            self.assertEqual((seg.annexe, seg.numero), ('XIV', 2), b)
        print("    OK SIG8-8 branches corporelles -> XIV-2 protection du "
              "revenu (`'corporel'` les capturait vers la RC generale)")

    def test_dix_sept_branches_donnent_sept_couples_et_non_trois(self):
        couples = {(SEGMENTS_S2[_segment_choisi(b)].sigma_prime,
                    SEGMENTS_S2[_segment_choisi(b)].sigma_reserve)
                   for b in ROUTAGE}
        self.assertGreaterEqual(len(couples), 7,
                                "l'aiguillage a cesse de discriminer")
        print(f"    OK SIG8-9 {len(ROUTAGE)} branches -> {len(couples)} couples "
              f"de sigma distincts (3 avant le lot)")


# =============================================================================
#  3. CE QUE L'AGENT PUBLIE
# =============================================================================

class T3_Sorties(unittest.TestCase):

    def test_les_sigma_publies_sont_ceux_du_segment(self):
        for b in ('rc_auto', 'protection_juridique', 'credit_caution',
                  'dommage_corporel_individuel'):
            r = _run(b)
            self.assertTrue(r['success'], r.get('erreur'))
            c = r['chocs_s2']
            seg = SEGMENTS_S2[_segment_choisi(b)]
            self.assertAlmostEqual(c['sigma_primes'], seg.sigma_prime, msg=b)
            self.assertAlmostEqual(c['sigma_reserves'], seg.sigma_reserve, msg=b)
            self.assertEqual(c['segment_s2'], _segment_choisi(b))
        print("    OK SIG8-10 sigma publies == sigma du segment, sur 4 branches")

    def test_la_reference_reglementaire_est_publiee(self):
        r = _run('dommage_corporel_individuel')
        ref = r['chocs_s2']['reference_s2']
        self.assertIn('Annexe XIV', ref)
        self.assertIn('segment 2', ref)
        print(f"    OK SIG8-11 reference publiee : « {ref} »")


# =============================================================================
#  4. LE DÉFAUT QUI RESTE — DOCUMENTÉ, PAS OUBLIÉ
# =============================================================================

class T4_Facteur_3_Article_115(unittest.TestCase):
    """Le SCR souscription d'A8 vaut le TIERS de sa valeur réglementaire.

    L'article 115 pose SCR = 3 × σ_nl × V_nl ; A8 s'arrête à σ_nl × V_nl,
    là où A10 applique bien le facteur 3. Ce défaut porte sur la FORMULE et
    non sur les écarts types : il n'entre pas dans le périmètre du lot B10-c,
    qui réconcilie les σ, et il triplerait ce module.

    Le test ci-dessous est en `expectedFailure` — idiome déjà employé dans ce
    dépôt pour documenter un défaut connu. Il échoue tant que le facteur 3
    manque, et le jour où on le corrige il passera en « unexpected success »,
    ce qui obligera à revenir ici.
    """

    def _termes(self, branche='rc_generale'):
        r = _run(branche)
        c = r['chocs_s2']
        be = r['be_utilise']
        prime = c['scr_primes'] / c['sigma_primes']
        return c, be, prime

    def test_le_rapport_a_la_formule_reglementaire_vaut_exactement_trois(self):
        """Ce que la mesure DIT aujourd'hui — et qui n'est pas conforme."""
        c, be, prime = self._termes()
        sp, sr = c['sigma_primes'], c['sigma_reserves']
        reglementaire = 3.0 * np.sqrt((sp * prime) ** 2
                                      + (sp * prime) * (sr * be)
                                      + (sr * be) ** 2)
        self.assertAlmostEqual(reglementaire / c['scr_souscription'], 3.0,
                               places=6)
        a, b = (f"{v:,.0f}".replace(',', ' ')
                for v in (c['scr_souscription'], reglementaire))
        print(f"    OK SIG8-12 ecart mesure a l'art. 115 : facteur 3,000000 "
              f"(A8 {a} contre {b})")

    @unittest.expectedFailure
    def test_le_facteur_3_de_larticle_115_est_applique(self):
        """DÉFAUT CONNU, NON CORRIGÉ — cf. la docstring de la classe."""
        c, be, prime = self._termes()
        sp, sr = c['sigma_primes'], c['sigma_reserves']
        reglementaire = 3.0 * np.sqrt((sp * prime) ** 2
                                      + (sp * prime) * (sr * be)
                                      + (sr * be) ** 2)
        self.assertAlmostEqual(c['scr_souscription'], reglementaire, delta=1.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
