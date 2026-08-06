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

 ⚠️ ET A8 N'A JAMAIS LU CE FICHIER — voir `_bloc_reference` plus bas. La
 duplication des paramètres de la formule standard subsiste, et ce filet est
 seul à la surveiller.

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
from direction_non_vie.reglementation.a10_solvabilite2.agent import DURATION_LOB


def _bloc_reference(nom):
    """La valeur ATTENDUE d'un bloc — recopiée du texte, pas lue du module.

    ⚠️ CETTE FONCTION A CHANGÉ DE SOURCE, ET C'EST LE LOT QUI L'EXIGE. Elle
    lisait `reference_actuaria.json` en le décrivant comme « la source qu'A8
    consomme » — description que le lot R5 avait déjà corrigée : A8 ne l'a
    jamais lue. Le bloc `parametres_scr_standard` a maintenant quitté ce
    fichier, comme les six écarts types l'avaient quitté au lot B10-c.

    ⚠️ ET ELLE NE LIT SURTOUT PAS `parametres_fs.py`. Un test qui importerait
    la table qu'il vérifie ne vérifierait RIEN : il constaterait qu'une
    variable est égale à elle-même. C'est la règle posée par
    `test_a7_sigma_s2.py` — la duplication EST le mécanisme, et elle est
    volontaire. La recopie ci-dessous vient du RÈGLEMENT, relu article par
    article ; si les deux divergent un jour, c'est au texte qu'il faut
    retourner, pas à l'autre copie.
    """
    return _RECOPIE_INDEPENDANTE[nom]


#: ⚠️ RECOPIE INDEPENDANTE, ET C'EST LE MECANISME MEME.
#:
#: Ce tableau duplique `parametres_fs.py`. Un test qui IMPORTERAIT la table
#: qu'il verifie ne verifierait rien -- c'est la lecon posee par
#: `test_a7_sigma_s2.py` au chantier B10. Si les deux divergent un jour, il
#: faut retourner au TEXTE OFFICIEL, pas a l'autre copie.
#:
#: ⚠️ ET LES VALEURS CI-DESSOUS ONT ETE RELUES DANS LE REGLEMENT DELEGUE
#: le 2026-08-06, article par article, texte consolide au 02.08.2022 :
#:      art. 166 par. 1  hausse des taux, echeance 10 ans ....... 42 %
#:      art. 167 par. 1  baisse des taux, echeance 10 ans ....... 31 %
#:      art. 169 par. 1 c)  actions de type 1 .................... 39 %
#:      art. 169 par. 2 c)  actions de type 2 .................... 49 %
#:      art. 174            actifs immobiliers ................... 25 %
#:      art. 176 par. 3     spread, echelon 0, duration <= 5 ans .. 0,9 %
#:      art. 188 par. 3-4   devise ............................... 25 %
#: Les facteurs catastrophe, eux, ne sont PAS dans le texte : l'art. 121
#: calibre sur les sommes assurees par region, donnee absente du depot.
_RECOPIE_INDEPENDANTE = {
    'scr_marche': {
        'choc_taux_hausse_10ans_relatif': 0.42,
        'choc_taux_baisse_10ans_relatif': -0.31,
        'choc_actions_type1': 0.39,
        'choc_actions_type2': 0.49,
        'choc_immobilier': 0.25,
        'choc_spread_IG': 0.009,
        'choc_devise': 0.25,
    },
    'scr_souscription_non_vie': {
        'facteur_catastrophe_vent': 0.10,
        'facteur_catastrophe_grele': 0.03,
        'facteur_catastrophe_inondation': 0.04,
    },
    'mcr': {
        'pct_scr_min': 0.25,
        'pct_scr_max': 0.45,
        'seuil_absolu_non_vie': 2_500_000.0,
        'alpha_primes': 0.0418,
        'beta_provisions': 0.0261,
    },
}

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

    def test_le_json_ne_porte_plus_de_parametres_reglementaires(self):
        """⚠️ LE TEST A CHANGE D'OBJET, ET IL EST PLUS FORT.


        Il verifiait que les six sigma avaient quitte `reference_actuaria.
        json`. Le bloc `parametres_scr_standard` ENTIER l'a quitte depuis :
        les parametres de la formule standard vivent dans `parametres_fs.py`.
        Il exige donc desormais que ce fichier ne porte PLUS AUCUN parametre
        reglementaire -- ni sigma, ni choc, ni borne de MCR. La regle est
        plus large que celle qu'elle remplace, et elle ne peut pas se perimer
        sur un nom particulier.
        """
        chemin = (Path(A8.__file__).resolve().parents[3]
                  / 'data' / 'marche' / 'reference_actuaria.json')
        self.assertTrue(chemin.is_file(), f"introuvable : {chemin}")
        ref = json.load(io.open(chemin, encoding='utf-8'))
        self.assertNotIn('parametres_scr_standard', ref,
                         "le bloc des parametres reglementaires est revenu "
                         "dans le fichier de donnees marche")
        plat = json.dumps(ref, ensure_ascii=False)
        for cle in tuple(self.CLES) + ('choc_taux_hausse', 'pct_scr_min',
                                       'facteur_catastrophe_vent'):
            self.assertNotIn(f'"{cle}"', plat,
                             f"{cle} est revenu dans le JSON")
        print(f"    OK SIG8-1 le fichier marche ne porte plus aucun "
              f"parametre reglementaire ({len(ref)} blocs restants)")

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

class T4_Formule_Articles_115_Et_117(unittest.TestCase):
    """Les trois corrections du lot B10-d.

    Le facteur 3 de l'article 115 manquait — ce module valait le tiers de sa
    valeur réglementaire. Il était documenté ici par un `expectedFailure`,
    remplacé par les vérifications de conformité ci-dessous : le signal a
    joué son rôle, il n'a plus lieu d'être.
    """

    def _termes(self, branche='rc_generale'):
        r = _run(branche)
        c = r['chocs_s2']
        prime = c['scr_primes'] / c['sigma_primes']
        return c, r['be_utilise'], prime

    def test_le_facteur_3_de_larticle_115_est_applique(self):
        """SCR = 3 × σ_nl × V_nl, et non σ_nl × V_nl."""
        for branche in ('rc_generale', 'rc_auto', 'protection_juridique'):
            c, be, prime = self._termes(branche)
            sp, sr = c['sigma_primes'], c['sigma_reserves']
            attendu = 3.0 * np.sqrt((sp * prime) ** 2 + (sp * prime) * (sr * be)
                                    + (sr * be) ** 2)
            self.assertAlmostEqual(c['scr_souscription'], attendu, delta=1.0,
                                   msg=branche)
        print("    OK SIG8-12 SCR souscription = 3 x racine(art. 117(2)) "
              "sur 3 branches — art. 115")

    def test_le_choc_de_taux_est_lu_comme_relatif(self):
        """0,48 est un facteur relatif au taux, pas 48 points de pourcentage."""
        r = _run('rc_auto')
        c = r['chocs_s2']
        rfr = c['rfr_calibrage'] / 100.0
        choc = _bloc_reference('scr_marche')['choc_taux_hausse_10ans_relatif']
        attendu = r['be_utilise'] * c['duration_passifs'] * choc * rfr
        self.assertAlmostEqual(c['scr_taux_hausse'], attendu, delta=1.0)
        print(f"    OK SIG8-13 choc de taux relatif : "
              f"{c['scr_taux_hausse']:,.0f} EUR".replace(',', ' '))

    def test_le_scr_de_taux_ne_depasse_plus_le_passif(self):
        """Le garde-fou de bon sens : il valait 168 % du Best Estimate.

        Une dette de duration quelques années ne peut pas perdre plus que sa
        valeur sur un mouvement de taux. Ce test tombe si quelqu'un rebranche
        une lecture absolue.
        """
        for branche in ('rc_auto', 'rc_medicale', 'construction'):
            r = _run(branche)
            part = r['chocs_s2']['scr_taux'] / r['be_utilise']
            self.assertLess(part, 0.50,
                            f"{branche} : SCR de taux a {part:.0%} du BE")
        print("    OK SIG8-14 SCR de taux < 50 % du BE sur 3 branches "
              "(il valait 168 %)")

    def test_la_duration_vient_de_la_branche(self):
        """Elle valait 3,5 ans en dur pour toutes les branches."""
        vues = {}
        for branche in ('rc_auto', 'mrh', 'rc_medicale', 'construction'):
            c = _run(branche)['chocs_s2']
            vues[branche] = c['duration_passifs']
            self.assertEqual(c['duration_passifs'],
                             DURATION_LOB[c['branche_normalisee']], branche)
        self.assertGreaterEqual(len(set(vues.values())), 3,
                                "la duration ne discrimine plus les branches")
        print(f"    OK SIG8-15 duration par branche : {vues}")


# =============================================================================
#  5. RISQUE OPÉRATIONNEL — ARTICLE 204
# =============================================================================

class T5_Article_204(unittest.TestCase):
    """Trois défauts corrigés au lot B10-e, tous sourcés."""

    def test_les_coefficients_sont_ceux_du_non_vie(self):
        """0,04 sur les primes était le coefficient de la VIE (art. 204(3))."""
        self.assertAlmostEqual(A8.OP_TAUX_PRIMES_NON_VIE, 0.03)
        self.assertAlmostEqual(A8.OP_TAUX_PROVISIONS_NON_VIE, 0.03)
        r = _run('rc_auto')
        c = r['chocs_s2']
        prime = c['scr_primes'] / c['sigma_primes']
        attendu = max(0.03 * prime, 0.03 * r['be_utilise'])
        self.assertAlmostEqual(c['op_base'], round(attendu, 2), delta=1.0)
        print(f"    OK SIG8-16 Op = max(3 % primes ; 3 % provisions) = "
              f"{c['op_base']:,.0f} EUR".replace(',', ' '))

    def test_le_coefficient_des_provisions_nest_plus_dix_fois_trop_bas(self):
        """Il valait 0,003 pour 0,03 — un ordre de grandeur (art. 204(4))."""
        r = _run('rc_auto')
        self.assertAlmostEqual(A8.OP_TAUX_PROVISIONS_NON_VIE
                               / A8.OP_TAUX_PRIMES_NON_VIE, 1.0, places=9,
                               msg="les deux coefficients non-vie sont egaux")
        self.assertGreater(0.03 * r['be_utilise'], 0.003 * r['be_utilise'] * 9)
        print("    OK SIG8-17 coefficient provisions 0,003 -> 0,03 (art. 204(4))")

    def test_le_plafond_de_trente_pourcent_du_bscr_est_applique(self):
        """Art. 204(1) : SCR_op = min(0,3 x BSCR ; Op)."""
        self.assertAlmostEqual(A8.OP_PLAFOND_BSCR, 0.30)
        r = _run('rc_auto')
        s, c = r['scr_total'], r['chocs_s2']
        self.assertAlmostEqual(s['scr_operationnel'],
                               min(0.30 * s['bscr'], c['op_base']), delta=1.0)
        self.assertLessEqual(s['scr_operationnel'], 0.30 * s['bscr'] + 1e-6)
        print(f"    OK SIG8-18 SCR_op = min(30 % x BSCR ; Op) = "
              f"{s['scr_operationnel']:,.0f} (plafond mord : "
              f"{s['op_plafonne']})".replace(',', ' '))


# =============================================================================
#  6. STRUCTURE D'AGRÉGATION — ARTICLES 114, 87 ET 103 DE LA DIRECTIVE
# =============================================================================

class T6_Structure_Agregation(unittest.TestCase):
    """Une matrice 4×4 plate est devenue deux étages plus une addition."""

    def test_le_module_non_vie_suit_la_matrice_de_larticle_114(self):
        r = _run('rc_auto')
        s, c = r['scr_total'], r['chocs_s2']
        v = np.array([c['scr_souscription'], c['scr_catastrophe'],
                      c['scr_cessation']])
        attendu = float(np.sqrt(v @ A8.CORR_NON_VIE @ v))
        self.assertAlmostEqual(s['scr_non_vie'], attendu, delta=1.0)
        self.assertEqual(A8.CORR_NON_VIE[0][1], 0.25)
        self.assertEqual(A8.CORR_NON_VIE[0][2], 0.00)
        print(f"    OK SIG8-19 module non-vie art. 114 (3x3) = "
              f"{s['scr_non_vie']:,.0f} EUR".replace(',', ' '))

    def test_le_scr_operationnel_est_ADDITIONNE_et_non_correle(self):
        """Art. 204(1) le calcule DEPUIS le BSCR : il ne peut pas y être.

        C'est la preuve structurelle du lot : `SCR_op = min(0,3 x BSCR ; Op)`
        serait circulaire si l'opérationnel était une composante du BSCR.
        """
        r = _run('rc_auto')
        s = r['scr_total']
        self.assertAlmostEqual(s['scr_total'],
                               s['bscr'] + s['scr_operationnel'], delta=1.0)
        self.assertGreater(s['scr_operationnel'], 0)
        print(f"    OK SIG8-20 SCR = BSCR + SCR_op = {s['bscr']:,.0f} + "
              f"{s['scr_operationnel']:,.0f} = {s['scr_total']:,.0f}"
              .replace(',', ' '))

    def test_le_bscr_nagrege_que_le_non_vie_et_le_marche(self):
        r = _run('rc_auto')
        s = r['scr_total']
        v = np.array([s['scr_non_vie'], s['scr_marche']])
        corr = np.array([[1.0, A8.CORR_NON_VIE_MARCHE],
                         [A8.CORR_NON_VIE_MARCHE, 1.0]])
        self.assertAlmostEqual(s['bscr'], float(np.sqrt(v @ corr @ v)),
                               delta=1.0)
        montant = f"{s['bscr']:,.0f}".replace(',', ' ')
        print(f"    OK SIG8-21 BSCR art. 87 = {montant} EUR "
              f"(correlation non-vie/marche {A8.CORR_NON_VIE_MARCHE} — "
              f"annexe IV de la DIRECTIVE, autre document)")

    def test_la_cessation_est_nulle_et_dite_comme_telle(self):
        """Art. 118 : calcul contrat par contrat, hors des entrées d'A8."""
        self.assertEqual(_run('rc_auto')['chocs_s2']['scr_cessation'], 0.0)
        print("    OK SIG8-22 cessation art. 118 = 0 — donnees contrat par "
              "contrat jamais recues ; le SCR non-vie est un MINORANT")


# =============================================================================
#  7. CHOCS DE TAUX — ARTICLES 166 ET 167
# =============================================================================

class T7_Articles_166_Et_167(unittest.TestCase):

    def test_les_valeurs_sont_celles_des_tables_a_dix_ans(self):
        m = _bloc_reference('scr_marche')
        self.assertAlmostEqual(m['choc_taux_hausse_10ans_relatif'], 0.42)
        self.assertAlmostEqual(m['choc_taux_baisse_10ans_relatif'], -0.31)
        print("    OK SIG8-23 hausse 42 % (art. 166), baisse 31 % (art. 167) "
              "— valaient 48 % et 38 %, absentes des deux tables")

    def test_le_plancher_dun_point_est_applique(self):
        """Art. 166(2) : la hausse vaut au moins un point de pourcentage."""
        self.assertAlmostEqual(A8.PLANCHER_HAUSSE_TAUX, 0.01)
        r = _run('rc_auto')
        c = r['chocs_s2']
        rfr = c['rfr_calibrage'] / 100.0
        choc = _bloc_reference('scr_marche')['choc_taux_hausse_10ans_relatif']
        attendu = (r['be_utilise'] * c['duration_passifs']
                   * max(choc * rfr, 0.01))
        self.assertAlmostEqual(c['scr_taux_hausse'], attendu, delta=1.0)
        print(f"    OK SIG8-24 plancher +1 pt applique ; a RFR="
              f"{rfr:.2%} il ne mord pas ({choc * rfr:.4f} > 0,0100), "
              f"il mordrait sous {0.01 / choc:.2%}")

    def test_la_baisse_est_nulle_a_taux_negatif(self):
        """Art. 167(2), vérifié sur la fonction elle-même."""
        agent = A8.AgentA8StressTesting(models_path='/tmp', audit_path='/tmp',
                                        verbose=False)
        params = {'scr_souscription_non_vie': {'facteur_catastrophe_vent': 0.10},
                  'scr_marche': _bloc_reference('scr_marche')}
        for rfr, attendu_nul in ((0.032, False), (-0.005, True)):
            c = agent._chocs_s2(be=3_000_000.0, prime=5_000_000.0,
                                p99_5=3_600_000.0, scr_params=params,
                                oat_10ans=0.0365, rfr_10ans=rfr,
                                inflation=0.024, branche='rc_auto',
                                tail_f=1.037)
            if attendu_nul:
                self.assertEqual(c['scr_taux_baisse'], 0.0)
            else:
                self.assertGreater(c['scr_taux_baisse'], 0.0)
        print("    OK SIG8-25 baisse nulle a taux negatif (art. 167(2))")


if __name__ == '__main__':
    unittest.main(verbosity=2)
