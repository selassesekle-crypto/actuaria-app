# =============================================================================
#  Tests — nv_triangle_builder.py :: construire()
#
#  FILET DE CARACTÉRISATION. `construire()` est le point d'entrée de
#  actuaria_app.py (4 sites d'appel, 13 clés de résultat consommées) et n'avait
#  AUCUN test. Ce fichier fige son contrat avant toute réduction future.
#
#  Il couvre les 4 formes d'appel réelles de l'application et les 4 valeurs de
#  `mode_declare` qu'elle propose ('auto' | 'cumule' | 'non_cumule' | 'brutes').
#
#  ─────────────────────────────────────────────────────────────────────────────
#  ⚠️ CORRECTION DOCUMENTÉE (lot 8c) — DÉCALAGE DES ANNÉES À LA SÉPARATION LLT
#
#  `_separer_triangles` construisait ses deux sous-triangles à la main en
#  redérivant `annee_min` du SOUS-ENSEMBLE. Les lignes étaient donc DÉCALÉES :
#  un grand sinistre survenu en 2021 dans un portefeuille commençant en 2019
#  atterrissait ligne 0 au lieu de ligne 2.
#
#      année du gros   ligne attendue   AVANT   APRÈS
#          2019              0            0       0
#          2020              1            0 ←     1
#          2021              2            0 ←     2
#          2022              3            0 ←     3
#
#  Conséquences mesurées : `attritionnel + grands != total` (écart 1 250 000 €
#  sur le jeu de test), et surtout la réserve grands sinistres calculée par
#  l'application (actuaria_app.py:1951 — à partir de 20 grands sinistres, un A7
#  complet tourne sur ce triangle) portait sur des années fausses.
#
#  Corrigé en déléguant à `construire_depuis_long` (module 4) avec le repère
#  d'années de la source COMPLÈTE imposé aux deux sous-ensembles. Les classes
#  T2 et T3 ci-dessous verrouillent le comportement corrigé.
# =============================================================================

import io
import unittest

import numpy as np
import pandas as pd

from direction_non_vie.services.nv_triangle_builder import NVTriangleBuilder

# Les 13 clés que actuaria_app.py lit sur le résultat (relevées site par site).
CLES_CONSOMMEES_PAR_L_APP = (
    'success', 'erreur', 'rapport', 'triangle_total', 'triangle_attritional',
    'triangle_grands', 'grands_sinistres', 'llt_utilise', 'llt_suggere',
    'statistiques', 'mode_separation', 'recommandation_grands',
    'diagnostic_qualite',
)

TRI_CUM = np.array([[1000., 1800., 2200., 2400.],
                    [1100., 1950., 2380.,    0.],
                    [1250., 2150.,    0.,    0.],
                    [1300.,    0.,    0.,    0.]])
TRI_INC = np.array([[1000.,  800.,  400.,  200.],
                    [1100.,  850.,  430.,    0.],
                    [1250.,  900.,    0.,    0.],
                    [1300.,    0.,    0.,    0.]])


def portefeuille(annee_du_gros: int) -> pd.DataFrame:
    """Petits sinistres sur 2019-2022 + UN gros sinistre sur une seule année.

    Le gros se déplace d'année en année : c'est ce qui révèle le décalage, un
    sous-ensemble qui ne couvre pas la première année du portefeuille.
    """
    lignes = []
    for ay in range(2019, 2023):
        for k in range(30):
            for d in range(0, 2022 - ay + 1):
                lignes.append({'sinistre_id': f'S{ay}{k:03d}', 'annee_survenance': ay,
                               'annee_developpement': d, 'montant': 1000.0})
    for d in range(0, 2022 - annee_du_gros + 1):
        lignes.append({'sinistre_id': 'LEGROS', 'annee_survenance': annee_du_gros,
                       'annee_developpement': d, 'montant': 500_000.0})
    return pd.DataFrame(lignes)


class _Upload(io.BytesIO):
    """Imite un upload Streamlit : un buffer QUI PORTE UN NOM — le lecteur
    choisit son moteur sur `getattr(source, 'name', '')`."""
    name = 'triangle.xlsx'


class T1_Contrat_Avec_L_Application(unittest.TestCase):
    """Les 4 formes d'appel réelles de actuaria_app.py aboutissent, et rendent
    les 13 clés qu'elle lit."""

    def _verifier(self, res, libelle):
        for cle in CLES_CONSOMMEES_PAR_L_APP:
            self.assertIn(cle, res, f"{libelle} : clé '{cle}' absente du résultat")
        self.assertTrue(res['success'], f"{libelle} : {res.get('erreur')}")
        self.assertIsInstance(res['rapport'], dict)
        self.assertIn('alertes', res['rapport'])
        self.assertIn('infos', res['rapport'])

    def test_site_donnees_individuelles_avec_llt(self):
        """actuaria_app.py:3313 — DataFrame individuel, llt, annee_debut."""
        r = NVTriangleBuilder(verbose=False).construire(
            source=portefeuille(2021), llt=100_000.0, annee_debut=2019)
        self._verifier(r, 'individuel + llt')
        self.assertEqual(r['mode_separation'], 'attritional_grands')
        print("    OK 8c-a site individuel + LLT : séparation active, 13 clés rendues")

    def test_site_triangle_declare_cumule(self):
        """actuaria_app.py:3524 — DataFrame matriciel, mode déclaré."""
        r = NVTriangleBuilder(verbose=False).construire(
            source=pd.DataFrame(TRI_CUM), mode_declare='cumule')
        self._verifier(r, 'triangle cumulé')
        self.assertAlmostEqual(float(r['triangle_total'].sum()), 17_530.0, delta=1.0)
        print("    OK 8c-b site triangle cumulé : total 17 530")

    def test_site_triangle_declare_non_cumule(self):
        """actuaria_app.py:2224 — 'non_cumule' doit cumuler vers le même total."""
        r = NVTriangleBuilder(verbose=False).construire(
            source=pd.DataFrame(TRI_INC), mode_declare='non_cumule')
        self._verifier(r, 'triangle incrémental')
        self.assertAlmostEqual(float(r['triangle_total'].sum()), 17_530.0, delta=1.0)
        print("    OK 8c-c site 'non_cumule' : cumulé au même total que 'cumule'")

    def test_site_upload_avec_onglet(self):
        """actuaria_app.py:1899 — upload Excel multi-onglets + nom_onglet."""
        buf = _Upload()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            pd.DataFrame(TRI_INC).to_excel(w, sheet_name='autre', index=False)
            pd.DataFrame(TRI_CUM).to_excel(w, sheet_name='bon', index=False)
        buf.seek(0)
        r = NVTriangleBuilder(verbose=False).construire(
            source=buf, mode_declare='cumule', nom_onglet='bon')
        self._verifier(r, 'upload + onglet')
        self.assertAlmostEqual(float(r['triangle_total'].sum()), 17_530.0, delta=1.0)
        print("    OK 8c-d site upload + onglet : le BON onglet est lu")

    def test_mode_brutes_force_les_donnees_individuelles(self):
        r = NVTriangleBuilder(verbose=False).construire(
            source=portefeuille(2020), mode_declare='brutes', llt=100_000.0)
        self._verifier(r, "mode 'brutes'")
        self.assertEqual(r['mode_separation'], 'attritional_grands')
        print("    OK 8c-e mode 'brutes' : données individuelles, séparation active")

    def test_ndarray_direct(self):
        r = NVTriangleBuilder(verbose=False).construire(
            source=TRI_CUM.copy(), mode_declare='cumule')
        self._verifier(r, 'ndarray')
        print("    OK 8c-f ndarray accepté directement")

    def test_llt_sur_agrege_avertit_sans_echouer(self):
        """Un LLT sur un triangle agrégé est impossible — averti, pas fatal."""
        r = NVTriangleBuilder(verbose=False).construire(
            source=pd.DataFrame(TRI_CUM), mode_declare='cumule', llt=50_000.0)
        self._verifier(r, 'llt sur agrégé')
        self.assertEqual(r['mode_separation'], 'aucun')
        self.assertTrue(any('LLT fourni' in a for a in r['rapport']['alertes']))
        print("    OK 8c-g LLT sur agrégé : averti, séparation ignorée, pas d'échec")


class T2_Correction_Du_Decalage_Des_Annees(unittest.TestCase):
    """LE VERROU DE LA CORRECTION. Voir le tableau AVANT/APRÈS en en-tête."""

    def test_le_gros_sinistre_atterrit_sur_son_annee(self):
        """AVANT : ligne 0 quelle que soit l'année. APRÈS : la bonne ligne."""
        for annee in (2019, 2020, 2021, 2022):
            with self.subTest(annee=annee):
                r = NVTriangleBuilder(verbose=False).construire(
                    source=portefeuille(annee), llt=100_000.0)
                G = r['triangle_grands']
                lignes = [i for i in range(G.shape[0]) if abs(G[i]).sum() > 0]
                self.assertEqual(
                    lignes, [annee - 2019],
                    f"gros sinistre de {annee} attendu ligne {annee - 2019}, "
                    f"trouvé lignes {lignes}")
        print("    OK 8c-h décalage corrigé : 2019→0, 2020→1, 2021→2, 2022→3")

    def test_attritionnel_plus_grands_egale_total(self):
        """L'invariant que le décalage cassait (écart mesuré : 1 250 000 €)."""
        for annee in (2019, 2020, 2021, 2022):
            with self.subTest(annee=annee):
                r = NVTriangleBuilder(verbose=False).construire(
                    source=portefeuille(annee), llt=100_000.0)
                ecart = float(np.abs(
                    r['triangle_total']
                    - (r['triangle_attritional'] + r['triangle_grands'])).max())
                self.assertLess(ecart, 1e-6)
        print("    OK 8c-i recombinaison exacte : attritionnel + grands == total")

    def test_le_sous_ensemble_couvre_toutes_les_annees_du_portefeuille(self):
        """Les deux triangles gardent le repère du portefeuille entier, donc
        restent comparables et recombinables."""
        r = NVTriangleBuilder(verbose=False).construire(
            source=portefeuille(2022), llt=100_000.0)
        self.assertEqual(r['triangle_grands'].shape, r['triangle_total'].shape)
        self.assertEqual(r['triangle_attritional'].shape, r['triangle_total'].shape)
        print("    OK 8c-j repère commun : les 3 triangles ont la même forme")


class T3_Le_Builder_Ne_Construit_Plus_Lui_Meme(unittest.TestCase):
    """Verrou anti-régression : la construction des sous-triangles est DÉLÉGUÉE
    au module 4. Si quelqu'un réintroduit un pivot/cumsum local, ce test tombe —
    c'est ce code local qui portait le décalage."""

    def test_pas_de_cumul_local_dans_la_separation(self):
        import ast, inspect
        import direction_non_vie.services.nv_triangle_builder as mod
        src = inspect.getsource(mod.NVTriangleBuilder._separer_triangles)
        arbre = ast.parse(src.lstrip())
        appels = {n.func.attr for n in ast.walk(arbre)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        for interdit in ('cumsum', 'pivot', 'pivot_table'):
            self.assertNotIn(interdit, appels,
                             f"'{interdit}' réapparu dans _separer_triangles — "
                             f"la construction doit rester déléguée au module 4")
        self.assertIn('construire_depuis_long', src)
        print("    OK 8c-k délégation verrouillée : ni cumsum ni pivot en local")


if __name__ == '__main__':
    unittest.main()
