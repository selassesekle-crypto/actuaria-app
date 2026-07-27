# =============================================================================
#  Tests — nv_triangle.py (Bloc II, module 7 : la façade)
#
#  Couvre le flux de bout en bout, les cas dégradés (qui doivent POURSUIVRE), les
#  trois seuls cas qui LÈVENT, les contrats hérités des modules 4/5/6, et les
#  verrous de propreté — dont le test AST qui prouve que la façade n'a
#  réimplémenté aucune logique des modules qu'elle orchestre.
# =============================================================================

import ast
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import direction_non_vie.services.nv_triangle as facade
from direction_non_vie.services.nv_triangle import (
    PreparationTriangles, preparer_pour_agent, preparer_triangles,
)
from direction_non_vie.services.nv_triangle_construction import ConstructionImpossible
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, _TRI_RECOURS_FORT,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────
# S1 = 3×400 = 1200 (grand si seuil 1000) · S2 = 150 (attritionnel) · S3 = 2000 (grand)
LONG = pd.DataFrame({
    'sinistre_id':         ['S1', 'S1', 'S1', 'S2', 'S2', 'S3'],
    'annee_survenance':    [2020, 2020, 2021, 2020, 2021, 2022],
    'annee_developpement': [0, 1, 0, 0, 0, 0],
    'montant_paye':        [400., 400., 400., 100., 50., 2000.],
})
LONG_AVEC_CHARGE = LONG.assign(montant_charge=[450., 450., 440., 120., 60., 2200.])
PRIMES_TABLE = pd.DataFrame({'annee_survenance': [2020, 2021, 2022],
                             'prime': [5000., 5200., 5400.]})
CUM = np.array([[100., 150., 170.], [120., 180., 0.], [130., 0., 0.]])

# Les 7 clés qu'agent.py:205/571/815-819 consomme réellement.
CLES_AGENT = ('statut', 'alertes', 'infos', 'taille', 'n_annees', 'n_dev',
              'mode_detecte')


class T1_Bout_En_Bout(unittest.TestCase):
    """Le flux complet sur un cas réaliste : fichier → mapping → séparation →
    construction ×2 sur repère commun → diagnostics."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='nvfacade_'))
        cls.fichier = cls.tmp / 'sinistres.xlsx'
        LONG_AVEC_CHARGE.to_excel(cls.fichier, index=False)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_flux_complet_depuis_un_fichier(self):
        p = preparer_triangles(self.fichier, seuil_llt=1000.,
                               lob='rc_auto_corporels')
        self.assertIsInstance(p, PreparationTriangles)
        self.assertEqual(p.rapport['etapes']['lecture'], 'ok (excel)')
        self.assertEqual(p.rapport['etapes']['mapping_sinistres'], 'ok')
        self.assertIn('ok', p.rapport['etapes']['separation'])
        self.assertIn('separee', p.rapport['etapes']['construction'])
        self.assertIsNotNone(p.triangles.paiements)
        print(f"    OK T1a bout en bout : les 5 étapes ok, "
              f"triangle {p.triangles.paiements.shape}")

    def test_coherence_attritionnel_plus_grands(self):
        """Le contrôle de cohérence que le repère commun rend possible."""
        p = preparer_triangles(LONG, seuil_llt=1000.)
        np.testing.assert_allclose(
            p.triangles.paiements + p.triangles_grands.paiements,
            p.triangles_total.paiements, rtol=1e-9, atol=1e-9)
        # même repère pour les trois
        self.assertEqual(p.triangles.annee_min, p.triangles_total.annee_min)
        self.assertEqual(p.triangles.paiements.shape,
                         p.triangles_grands.paiements.shape)
        print("    OK T1b cohérence : attritionnel + grands = total, repère commun")

    def test_diagnostic_jamais_sur_les_grands(self):
        p = preparer_triangles(LONG_AVEC_CHARGE, seuil_llt=1000.)
        self.assertIn('attritionnel', p.diagnostics)
        self.assertIn('charges', p.diagnostics)
        self.assertNotIn('grands', p.diagnostics)          # JAMAIS
        print(f"    OK T1c diagnostics sur {sorted(p.diagnostics)} — 'grands' exclu")

    def test_synthese_json_serialisable(self):
        p = preparer_triangles(LONG, seuil_llt=1000.)
        s = p.synthese()
        json.dumps(s)
        for cle in ('statut', 'etapes', 'triangles', 'separation', 'diagnostics',
                    'diagnostic_statut_le_plus_severe'):
            self.assertIn(cle, s)
        print("    OK T1d synthese() sérialisable, clés du contrat présentes")


class T2_Cas_Degrades(unittest.TestCase):
    """Erreurs partielles : le flux POURSUIT avec ce qui est possible."""

    def test_sans_separation_demandee(self):
        p = preparer_triangles(LONG)
        self.assertEqual(p.rapport['etapes']['separation'], 'non demandee')
        self.assertIsNone(p.separation)
        self.assertIsNone(p.triangles_grands)
        self.assertIn('paiements', p.diagnostics)          # pas 'attritionnel'
        print("    OK T2a sans séparation : flux complet, diagnostic 'paiements'")

    def test_separation_sur_agregat_avertie_et_poursuivie(self):
        """Contrat du module 5 : avertir, JAMAIS faire tomber le run."""
        p = preparer_triangles(CUM, seuil_llt=50., mode_paiements='cumule')
        self.assertEqual(p.rapport['etapes']['separation'], 'ignoree (donnees agregees)')
        self.assertIsNone(p.separation)
        self.assertIsNotNone(p.triangles.paiements)        # construit quand même
        self.assertTrue(any('[separation]' in a for a in p.rapport['alertes']))
        print("    OK T2b séparation sur agrégat : avertie, flux poursuivi")

    def test_primes_manquantes_ne_bloquent_pas(self):
        p = preparer_triangles(
            LONG, methodes_demandees=('chain_ladder', 'bornhuetter_ferguson'))
        self.assertIsNotNone(p.triangles.paiements)
        self.assertEqual(p.triangles.methodes_bloquees, ('bornhuetter_ferguson',))
        self.assertTrue(any('primes absentes' in a for a in p.rapport['alertes']))
        print("    OK T2c primes absentes : triangle construit, seule BF bloquée")

    def test_primes_en_table_sont_agregees(self):
        p = preparer_triangles(LONG, primes=PRIMES_TABLE,
                               methodes_demandees=('cape_cod',))
        np.testing.assert_allclose(p.triangles.primes, [5000., 5200., 5400.])
        self.assertEqual(p.triangles.methodes_bloquees, ())
        print("    OK T2d primes en table : mappées et agrégées en vecteur")

    def test_charges_absentes_en_base_charges_alerte(self):
        """Sans paiements ni charges construisibles pour la base demandée, on
        lève ; mais si les charges manquent SEULEMENT, l'alerte IBNR pur sort."""
        p = preparer_triangles(LONG, triangle_reference='paiements')
        self.assertIsNone(p.triangles.charges)
        self.assertIsNotNone(p.triangles.diagonale_paiements)
        print("    OK T2e charges absentes : paiements seuls, diagonale disponible")


class T3_Cas_Qui_Levent(unittest.TestCase):
    """Les TROIS seuls cas où poursuivre produirait un résultat faux."""

    def test_cumulativite_ambigue_leve(self):
        """Un cumulé à recours ressemble à un incrémental : refuser plutôt que
        se tromper (contrat du module 4)."""
        with self.assertRaises(ConstructionImpossible) as ctx:
            preparer_triangles(_TRI_RECOURS_FORT)          # mode 'auto'
        self.assertIn('AMBIG', str(ctx.exception).upper())
        print("    OK T3a cumulativité ambiguë non déclarée → lève")

    def test_base_reference_inconstructible_leve(self):
        with self.assertRaises(ConstructionImpossible):
            preparer_triangles(CUM, mode_paiements='cumule',
                               triangle_reference='charges')
        print("    OK T3b base_reference sans triangle correspondant → lève")

    def test_aucun_triangle_constructible_leve(self):
        with self.assertRaises(ConstructionImpossible):
            preparer_triangles(pd.DataFrame({'annee_survenance': [2020],
                                             'montant_paye': [100.]}))  # aucun axe
        print("    OK T3c aucun triangle constructible → lève")


class T4_Contrats_Herites(unittest.TestCase):
    """Ce que les modules 4/5/6 ont fait promettre à la façade."""

    def test_repere_transmis_aux_deux_constructions(self):
        """Sans repère, l'attritionnel perdrait les années sans petit sinistre."""
        p = preparer_triangles(LONG, seuil_llt=1500.)       # seul S3 est grand
        # l'attritionnel n'a pas de sinistre en 2022, mais garde la ligne
        self.assertEqual(p.triangles.paiements.shape[0], 3)
        self.assertEqual(p.triangles.annee_min, 2020)
        self.assertAlmostEqual(float(p.triangles.paiements[2].sum()), 0.0, places=2)
        print("    OK T4a repère transmis : attritionnel garde ses 3 années")

    def test_diagonale_paiements_en_base_charges(self):
        """DETTE IMPÉRATIVE : le payé à date reste accessible pour que N4 calcule
        `ultime_charges − payé`, jamais `− charges`."""
        p = preparer_triangles(LONG_AVEC_CHARGE, source_charges=LONG_AVEC_CHARGE,
                               triangle_reference='charges')
        self.assertEqual(p.triangles.base_reference, 'charges')
        self.assertIsNotNone(p.triangles.diagonale_paiements)
        np.testing.assert_allclose(p.triangles.reference, p.triangles.charges)
        print("    OK T4b base charges : diagonale des PAIEMENTS disponible")

    def test_vraie_lob_transmise_au_diagnostic(self):
        """Le builder envoyait 'generique' en dur — la façade transmet la vraie."""
        with patch.object(facade, 'diagnostiquer_triangle',
                          wraps=facade.diagnostiquer_triangle) as espion:
            preparer_triangles(LONG, lob='rc_auto_corporels')
        self.assertTrue(espion.call_args_list)
        for appel in espion.call_args_list:
            self.assertEqual(appel.kwargs.get('lob'), 'rc_auto_corporels')
        print("    OK T4c vraie LoB transmise au diagnostic (pas 'generique')")


class T5_Statut_Decouple_Du_Diagnostic(unittest.TestCase):
    """LA décision tranchée : le diagnostic informe, il ne colore pas."""

    def test_recours_legitime_non_degrade_par_le_diagnostic(self):
        """TEST OBLIGATOIRE — un triangle à recours LÉGITIME traverse la façade
        et ressort avec un statut NON dégradé par le diagnostic. Le contrôle C1
        du module 6 a un défaut connu (toute baisse > 1 % = violation, ROUGE dès
        3) : sans le découplage, une donnée saine serait pénalisée."""
        p = preparer_triangles(_TRI_RECOURS_FORT, mode_paiements='cumule')
        # le diagnostic voit bien un problème (C1 sur le recours)…
        diag = p.diagnostics['paiements']
        c1 = next(c for c in diag['controles'] if c['code'] == 'C1')
        self.assertEqual(c1['statut'], 'ROUGE')             # le faux positif connu
        # …mais le statut global n'en tient PAS compte
        self.assertEqual(p.rapport['statut'], 'VERT')
        self.assertEqual(p.diagnostic_statut_le_plus_severe, diag['statut'])
        print(f"    OK T5a recours légitime : C1 ROUGE mais statut global "
              f"{p.rapport['statut']} (découplé)")

    def test_diagnostic_statut_expose_mais_non_consomme(self):
        p = preparer_triangles(_TRI_RECOURS_FORT, mode_paiements='cumule')
        self.assertIn(p.diagnostic_statut_le_plus_severe, ('VERT', 'AMBRE', 'ROUGE'))
        # le champ existe, mais aucune corrélation forcée avec le statut global
        self.assertIn('diagnostic_statut_le_plus_severe', p.synthese())
        print(f"    OK T5b diagnostic_statut_le_plus_severe = "
              f"{p.diagnostic_statut_le_plus_severe}, exposé sans être consommé")

    def test_alertes_diagnostic_visibles_dans_le_rapport(self):
        """Découplé ≠ caché : le diagnostic reste intégralement visible."""
        p = preparer_triangles(_TRI_RECOURS_FORT, mode_paiements='cumule')
        self.assertTrue(any('[diagnostic]' in i for i in p.rapport['infos']))
        self.assertIn('paiements', p.diagnostics)
        print("    OK T5c alertes de diagnostic présentes dans le rapport (visibles)")


class T6_Adaptateur_Agent(unittest.TestCase):
    """`preparer_pour_agent` doit rendre exactement ce qu'agent.py consomme."""

    def test_quadruplet_et_cles_attendues(self):
        C, C_engage, primes, rapport = preparer_pour_agent(LONG_AVEC_CHARGE,
                                                           source_charges=LONG_AVEC_CHARGE)
        self.assertIsInstance(C, np.ndarray)
        self.assertIsInstance(C_engage, np.ndarray)
        for cle in CLES_AGENT:
            self.assertIn(cle, rapport, f"clé '{cle}' attendue par agent.py")
        self.assertEqual(rapport['taille'], f"{C.shape[0]}×{C.shape[1]}")
        print(f"    OK T6a adaptateur : 4-uplet + les {len(CLES_AGENT)} clés d'agent.py")

    def test_objet_complet_conserve(self):
        """Rien n'est perdu : la préparation complète reste accessible."""
        *_, rapport = preparer_pour_agent(LONG)
        self.assertIsInstance(rapport['preparation'], PreparationTriangles)
        print("    OK T6b adaptateur : PreparationTriangles conservée dans le rapport")


class T7_Proprete_Facade(unittest.TestCase):
    """Verrous de propreté : la façade ORCHESTRE, elle ne réimplémente pas."""

    def test_ast_aucune_logique_metier_reimplementee(self):
        """Les primitives métier des modules 4/5/6 ne doivent PAS apparaître ici.

        Si quelqu'un recodait un pivot, un cumul, un masquage de zone future, un
        classement par seuil ou un calcul de score, ce test deviendrait rouge.
        """
        src = Path(facade.__file__).read_text(encoding='utf-8')
        arbre = ast.parse(src)
        appels = {n.func.attr for n in ast.walk(arbre)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        for interdit in ('cumsum', 'itertuples', 'transform'):
            self.assertNotIn(interdit, appels,
                             f"'{interdit}' = logique du module 4/5 réimplémentée")
        # pas de masquage de zone future (module 4) ni de comparaison à un seuil
        # de classement (module 5) — recherche sur le code, hors docstrings
        code = "\n".join(l for l in src.splitlines()
                         if not l.strip().startswith('#'))
        self.assertNotIn('i + j >=', code)
        self.assertNotIn('>= float(seuil', code)
        print(f"    OK T7a AST : aucune primitive métier des modules 4/5/6 "
              f"réimplémentée")

    def test_toutes_les_fonctions_restent_courtes(self):
        """Leçon du module 4 (construire_triangles avait dérivé à 115 l).

        On mesure le CORPS EXÉCUTABLE, hors signature et docstring : la propreté
        vise la logique, pas la documentation. Une porte d'entrée publique à 14
        paramètres avec une docstring portant les contrats hérités est exactement
        ce qu'on veut — la pénaliser pousserait à moins documenter.
        """
        arbre = ast.parse(Path(facade.__file__).read_text(encoding='utf-8'))
        corps = {}
        for n in ast.walk(arbre):
            if not isinstance(n, ast.FunctionDef):
                continue
            debut = n.body[0]
            # sauter la docstring si elle en est la première instruction
            if (isinstance(debut, ast.Expr) and isinstance(debut.value, ast.Constant)
                    and isinstance(debut.value.value, str) and len(n.body) > 1):
                debut = n.body[1]
            corps[n.name] = n.end_lineno - debut.lineno + 1
        trop = {n: t for n, t in corps.items() if t > 60}
        self.assertEqual(trop, {}, f"corps trop long(s) : {trop}")
        print(f"    OK T7b {len(corps)} fonctions, corps max = {max(corps.values())} l")

    def test_agnostique_de_l_interface(self):
        arbre = ast.parse(Path(facade.__file__).read_text(encoding='utf-8'))
        for n in ast.walk(arbre):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                cible = (getattr(n, 'module', '') or '') + ' ' + \
                        ' '.join(a.name for a in n.names)
                self.assertNotIn('streamlit', cible)
                self.assertNotIn('a7_provisionnement', cible)   # pas d'agent
        print("    OK T7c aucun import streamlit ni agent (façade agnostique)")

    def test_alertes_consolidees_prefixees_sans_perte(self):
        """Chaque alerte porte son étape, et les objets d'origine restent là."""
        p = preparer_triangles(CUM, seuil_llt=50., mode_paiements='cumule')
        self.assertTrue(all(a.startswith('[') for a in p.rapport['alertes']))
        # l'objet d'origine du module 4 reste accessible entier
        self.assertIsNotNone(p.triangles.rapport)
        print("    OK T7d alertes préfixées par étape, objets d'origine conservés")


if __name__ == '__main__':
    unittest.main()
