# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 Ibrahim — Benktander (1976) / Hovinen : filet
=============================================================================

 ⚠️ LE VERROU DU PÉRIMÈTRE EST ÉCRIT EN PREMIER, ET C'EST DÉLIBÉRÉ.

 Benktander est un MÉLANGE de Chain Ladder et de Bornhuetter-Ferguson :

     U_GB = α · U_CL + (1 − α) · U_BF        avec α = 1 / CDF

 Le faire entrer dans le Best Estimate rouvrirait le défaut corrigé au
 commit 6e2e66e, où le point estimate de Mack VALAIT Chain Ladder et où les
 deux étaient pondérés. Mesuré sur GenIns, α moyen = 0,7693 : avec quatre
 méthodes à poids égaux, Chain Ladder pèserait RÉELLEMENT 44,2 % et
 Bornhuetter-Ferguson 30,8 %, pendant que le tableau afficherait 25 % chacun.
 Cape Cod, seule méthode non dupliquée, tomberait à 25 % d'un total effectif
 de 1,00.

 La duplication serait PARTIELLE et VARIABLE PAR ANNÉE — α dépend de la
 maturité — donc invisible à la lecture. D'où un verrou structurel, sur
 l'arbre syntaxique de `n4_best_estimate.py`, et non une intention écrite
 dans un commentaire.
=============================================================================
"""

import ast
import inspect
import io
import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement import (
    n4_best_estimate as N4)

#: Les trois méthodes qui construisent le Best Estimate, et elles seules.
METHODES_DU_BE = {'chain_ladder', 'bornhuetter_ferguson', 'cape_cod'}


# =============================================================================
#  1. LE VERROU — BENKTANDER N'ENTRE JAMAIS DANS LE BEST ESTIMATE
# =============================================================================

class T1_Verrou_Perimetre(unittest.TestCase):

    def test_benktander_nest_pas_dans_les_methodes_du_be(self):
        self.assertNotIn('benktander', N4._CLES_N3)
        self.assertEqual(set(N4._CLES_N3), METHODES_DU_BE)
        print(f"    OK GB-1 méthodes du BE : {sorted(N4._CLES_N3)} — "
              f"Benktander absent")

    def test_la_table_des_methodes_est_un_litteral_de_trois_cles(self):
        """Contrôle sur l'ARBRE SYNTAXIQUE, pas sur l'objet en mémoire.

        Un test à l'exécution ne verrait pas un `_CLES_N3['benktander'] = …`
        ajouté plus loin, ni une construction par compréhension. Ici on exige
        que la table soit un dictionnaire LITTÉRAL de trois clés constantes :
        il devient impossible d'y glisser une quatrième méthode sans que ce
        test tombe.
        """
        arbre = ast.parse(inspect.getsource(N4))
        litteraux = [n.value for n in arbre.body
                     if isinstance(n, ast.Assign)
                     for c in n.targets
                     if isinstance(c, ast.Name) and c.id == '_CLES_N3']
        self.assertEqual(len(litteraux), 1,
                         "`_CLES_N3` doit être défini une fois et une seule")
        self.assertIsInstance(litteraux[0], ast.Dict,
                              "`_CLES_N3` doit rester un littéral")
        cles = {k.value for k in litteraux[0].keys}
        self.assertEqual(cles, METHODES_DU_BE)
        print(f"    OK GB-2 `_CLES_N3` est un littéral de {len(cles)} clés — "
              f"aucune quatrième méthode ne peut y entrer")

    def test_le_module_du_be_ignore_totalement_benktander(self):
        """N4 construit le Best Estimate : le mot ne doit pas y figurer."""
        src = inspect.getsource(N4)
        self.assertNotIn('benktander', src.lower(),
                         "le module du Best Estimate mentionne Benktander")
        print("    OK GB-3 `n4_best_estimate.py` ne mentionne pas Benktander")

    def test_aucune_mutation_de_la_table_nexiste_dans_le_depot(self):
        """Personne n'ÉCRIT dans `_CLES_N3`, nulle part dans le dépôt.

        Le contrôle est syntaxique et non textuel : `_CLES_N3[m]` en LECTURE
        est légitime — N4 s'en sert pour retrouver la clé N3 d'une méthode —
        alors que `_CLES_N3[x] = …`, `_CLES_N3.update(…)` ou
        `_CLES_N3.setdefault(…)` contournent le littéral. Un simple `in` sur
        le texte confondrait les deux ; l'arbre les sépare.
        """
        from pathlib import Path
        racine = Path(N4.__file__).resolve().parents[3]
        MUTATEURS = {'update', 'setdefault', 'pop', 'clear', '__setitem__'}
        coupables = []
        for chemin in sorted(racine.rglob('*.py')):
            if '__pycache__' in str(chemin):
                continue
            txt = io.open(chemin, encoding='utf-8', errors='ignore').read()
            if '_CLES_N3' not in txt:
                continue
            try:
                arbre = ast.parse(txt)
            except SyntaxError:
                continue
            for n in ast.walk(arbre):
                # _CLES_N3[...] = ...   /   del _CLES_N3[...]
                cibles = (list(n.targets) if isinstance(n, ast.Assign)
                          else [n.target] if isinstance(n, ast.AugAssign)
                          else list(n.targets) if isinstance(n, ast.Delete)
                          else [])
                for c in cibles:
                    if (isinstance(c, ast.Subscript)
                            and isinstance(c.value, ast.Name)
                            and c.value.id == '_CLES_N3'):
                        coupables.append(f'{chemin.name}:{n.lineno} affectation')
                # _CLES_N3.update(...) et compagnie
                if (isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and isinstance(n.func.value, ast.Name)
                        and n.func.value.id == '_CLES_N3'
                        and n.func.attr in MUTATEURS):
                    coupables.append(f'{chemin.name}:{n.lineno} .{n.func.attr}()')
        self.assertEqual(coupables, [],
                         f"mutation de `_CLES_N3` trouvée : {coupables}")
        print("    OK GB-4 aucune ÉCRITURE dans `_CLES_N3` dans tout le dépôt "
              "(les lectures `_CLES_N3[m]` de N4, elles, sont légitimes)")


# =============================================================================
#  2. LA FORMULE — VÉRIFIÉE, PAS SUPPOSÉE
# =============================================================================

def _contexte(avec_exposition=True):
    """Les entrées de Benktander, telles que l'agent les lui donne."""
    from direction_non_vie.provisionnement.a7_provisionnement.n3.chain_ladder \
        import chain_ladder, calculer_pct_developpe
    from direction_non_vie.provisionnement.a7_provisionnement.n3.bf_cape_cod \
        import bornhuetter_ferguson
    from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim \
        import GENINS
    C = np.asarray(GENINS, float)
    n = C.shape[0]
    rc = chain_ladder(C, tail_force=1.0)
    pct = np.asarray(calculer_pct_developpe(
        C, np.asarray(rc['facteurs_cumules'], float)), float)
    dern = np.array([C[i, min(n - i - 1, C.shape[1] - 1)] for i in range(n)])
    ucl = np.asarray(rc['ultimates'], float)
    expo = (np.full(n, float(np.mean(C[:, 0])) * 8.0) if avec_exposition
            else None)
    bf = bornhuetter_ferguson(C, pct, dern, ucl, exposition=expo, annee_base=1)
    return C, pct, dern, ucl, bf


class T2_Formule(unittest.TestCase):

    def test_les_deux_ecritures_du_guide_coincident(self):
        """U_GB = α·U_CL + (1−α)·U_BF   ⇔   IBNR_GB = (1−α)·U_BF.

        L'équivalence tient parce que α·U_CL = C. Elle est vérifiée ici sur
        les ultimes RÉELS de Chain Ladder, pas sur C/α : c'est le contrôle
        qui a du sens, puisque c'est ce couple-là que le rapport affiche.
        """
        from direction_non_vie.provisionnement.a7_provisionnement.n3.benktander \
            import benktander
        _C, pct, dern, ucl, bf = _contexte()
        gb = benktander(pct, dern, bf, annee_base=1)
        ubf = np.asarray(bf['ultimates'], float)
        ugb = np.asarray(gb['ultimates'], float)
        melange = pct * ucl + (1 - pct) * ubf
        rel = np.max(np.abs(melange - ugb) / np.maximum(np.abs(ugb), 1.0))
        self.assertLess(rel, 1e-5, f"écart relatif {rel:.2e} entre les deux "
                                   f"écritures du guide")
        print(f"    OK GB-5 les deux écritures coïncident — écart relatif "
              f"maximal {rel:.2e}")

    def test_benktander_se_place_a_alpha_du_chemin_bf_vers_cl(self):
        """La propriété qui définit la crédibilité, année par année."""
        from direction_non_vie.provisionnement.a7_provisionnement.n3.benktander \
            import benktander
        _C, pct, dern, ucl, bf = _contexte()
        gb = benktander(pct, dern, bf, annee_base=1)
        ubf = np.asarray(bf['ultimates'], float)
        ugb = np.asarray(gb['ultimates'], float)
        ecarts = []
        for i in range(1, len(ugb)):
            d = ucl[i] - ubf[i]
            if abs(d) < 1.0:
                continue
            ecarts.append(abs((ugb[i] - ubf[i]) / d - pct[i]))
        self.assertGreaterEqual(len(ecarts), 5, "trop peu d'années exploitables")
        self.assertLess(max(ecarts), 1e-3)
        print(f"    OK GB-6 position = α sur {len(ecarts)} années "
              f"(écart max {max(ecarts):.2e})")

    def test_la_reserve_reste_entre_chain_ladder_et_bornhuetter_ferguson(self):
        """Conséquence directe d'une combinaison convexe."""
        from direction_non_vie.provisionnement.a7_provisionnement.n3.benktander \
            import benktander
        from direction_non_vie.provisionnement.a7_provisionnement.n3.chain_ladder \
            import chain_ladder
        C, pct, dern, _ucl, bf = _contexte()
        gb = benktander(pct, dern, bf, annee_base=1)
        r_cl = chain_ladder(C, tail_force=1.0)['reserve_totale']
        bas, haut = sorted((r_cl, bf['reserve_totale']))
        self.assertGreaterEqual(gb['reserve_totale'], bas - 1.0)
        self.assertLessEqual(gb['reserve_totale'], haut + 1.0)
        print(f"    OK GB-7 réserve GB {gb['reserve_totale']:,.0f} entre BF "
              f"{bf['reserve_totale']:,.0f} et CL {r_cl:,.0f}"
              .replace(',', ' '))

    def test_sans_exposition_benktander_suit_bornhuetter_ferguson(self):
        """Il se déduit de BF : son indisponibilité doit se propager.

        On ne fabrique pas un zéro qui se lirait comme une réserve nulle —
        même motif que `libelle_loss_ratio`.
        """
        from direction_non_vie.provisionnement.a7_provisionnement.n3.benktander \
            import benktander
        _C, pct, dern, _ucl, bf = _contexte(avec_exposition=False)
        self.assertFalse(bf['disponible'])
        gb = benktander(pct, dern, bf, annee_base=1)
        self.assertFalse(gb['disponible'])
        self.assertEqual(gb['reserve_totale'], 0.0)
        self.assertIn('Bornhuetter-Ferguson', gb['message'])
        print("    OK GB-8 sans exposition : BF indisponible ⇒ GB "
              "indisponible, avec son motif")


# =============================================================================
#  3. LE BEST ESTIMATE NE BOUGE PAS — BOUT EN BOUT
# =============================================================================

class T3_Best_Estimate_Intact(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.provisionnement.a7_provisionnement.agent \
            import AgentA7Provisionnement
        from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim \
            import GENINS
        C = np.asarray(GENINS, float)
        expo = np.full(C.shape[0], float(np.mean(C[:, 0])) * 8.0)
        cls.r = AgentA7Provisionnement(verbose=False).run(
            source=C, primes=expo, mode_declare='cumule',
            generer_graphiques=False, generer_word=False,
            generer_pdf_flag=False, n_sim_bootstrap=200, seed=42)

    def test_benktander_est_calcule_mais_hors_du_be(self):
        n3, n4 = self.r['n3'], self.r['n4']
        self.assertTrue(n3['benktander']['disponible'])
        self.assertGreater(n3['benktander']['reserve_totale'], 0)
        self.assertNotIn('benktander', n4['methodes_incluses'])
        self.assertNotIn('benktander', n4.get('poids', {}))
        self.assertEqual(set(n4['methodes_incluses']) - METHODES_DU_BE, set())
        montant = f"{n3['benktander']['reserve_totale']:,.0f}".replace(",", " ")
        print(f"    OK GB-9 GB calculé ({montant}) et absent du BE — "
              f"méthodes retenues {sorted(n4['methodes_incluses'])}")

    def test_la_somme_des_poids_reste_a_un_sur_les_seules_methodes_du_be(self):
        poids = self.r['n4'].get('poids', {})
        self.assertAlmostEqual(sum(poids.values()), 1.0, places=6)
        self.assertTrue(set(poids) <= METHODES_DU_BE)
        print(f"    OK GB-10 Σ poids = 1,000000 sur {sorted(poids)} — "
              f"aucun poids n'a fuité vers Benktander")


# =============================================================================
#  4. LES TROIS FORMATS — SUR FICHIERS RÉELLEMENT GÉNÉRÉS
# =============================================================================

class T4_Trois_Formats(unittest.TestCase):
    """C'est là que les défauts apparaissent : Word tronquait 14 messages sur
    14 au lot Munich, l'Excel affichait « Annexe II » en dur au lot B10-c."""

    @classmethod
    def setUpClass(cls):
        cls.r = T3_Best_Estimate_Intact.__dict__['setUpClass'].__func__(
            T3_Best_Estimate_Intact) or T3_Best_Estimate_Intact.r

    def test_le_html_et_le_word_portent_benktander_et_sa_mention(self):
        from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport \
            import export_html, export_word
        r = T3_Best_Estimate_Intact.r
        n1, n2, n3, n4 = r.get('n1', {}), r['n2'], r['n3'], r['n4']
        html = export_html(n1=n1, n2=n2, n3=n3, n4=n4)
        for motif in ('Benktander', '1/CDF', 'INFORMATIVE'):
            self.assertIn(motif, html, f"HTML sans « {motif} »")
        mot = export_word(n1, n2, n3, n4)
        octets = mot if isinstance(mot, bytes) else mot.getvalue()
        self.assertGreater(len(octets), 10_000)
        import zipfile
        with zipfile.ZipFile(io.BytesIO(octets)) as z:
            txt = b''.join(z.read(n) for n in z.namelist()
                           if n.endswith(('.xml', '.rels'))).decode(
                               'utf-8', errors='ignore')
        for motif in ('Benktander', '1/CDF'):
            self.assertIn(motif, txt, f"Word sans « {motif} »")
        print(f"    OK GB-11 HTML {len(html):,} o et Word {len(octets):,} o "
              f"portent Benktander et sa mention".replace(',', ' '))

    def test_lexcel_porte_benktander_avec_le_bon_statut(self):
        """La cellule est RELUE : sonder les octets XML rate les accents.

        Le piège s'était déjà refermé au lot Munich, puis à nouveau ici sur
        le caractère α.
        """
        import openpyxl
        from direction_non_vie.provisionnement.a7_provisionnement.n5_excel \
            import export_excel
        from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim \
            import GENINS
        r = T3_Best_Estimate_Intact.r
        b = export_excel(np.asarray(GENINS, float), r.get('n1', {}),
                         r['n2'], r['n3'], r['n4'])
        octets = b if isinstance(b, bytes) else b.getvalue()
        wb = openpyxl.load_workbook(io.BytesIO(octets))
        trouvee = None
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str) and 'Benktander' in c.value:
                        trouvee = [x.value for x in row]
        self.assertIsNotNone(trouvee, "Benktander absent de l'Excel")
        texte = ' '.join(str(v) for v in trouvee if v is not None)
        self.assertIn('Informatif', texte,
                      "Benktander doit être « Informatif », jamais « Exclue » : "
                      "il n'est pas disqualifié, il est hors périmètre du BE")
        self.assertNotIn('Exclue', texte)
        self.assertIn('α', texte)
        taille = f"{len(octets):,}".replace(",", " ")
        print(f"    OK GB-12 Excel : ligne Benktander « ⓘ Informatif », α "
              f"présent ({taille} o)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
