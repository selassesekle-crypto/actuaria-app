"""CONTRÔLES POSITIFS — les scorecards et les statuts qu'un actuaire lit pour signer.

Cinq constats, **un seul geste** : *un compte publié doit être DÉRIVÉ de ce
qu'il compte, jamais écrit en dur* — et une docstring doit dire ce que son code
fait, ni plus ni moins.

  `a3/C9`  — scorecard : légende « 3 ✅ », liste de **4** items, **5**
             hypothèses calculées. `h5_deviance`, une PLAFONNANTE, n'apparaît
             nulle part. *Trois comptes différents pour la même chose, dans le
             même graphique.*
  `a3/C10` — la docstring annonce « convergence des 3 modèles » ; le code lit
             `poisson` et `gamma`, jamais le Tweedie.
  `a4/C6`  — « Modèles testés : 6/**8** » : le dénominateur est un littéral qui
             ne correspond ni aux 6 candidats, ni aux 10 du catalogue, ni aux 6
             réellement testés.
  `a4/C8`  — même scorecard, même légende figée à 3.
  `a4/C9`  — « ROUGE : aucun modèle ML ne bat le GLM », alors que le code rend
             AMBRE dès que le Gini ML dépasse un seuil `0.10` invisible.

⚠️⚠️ CES CINQ SONT MESURÉS COMME **ATTEIGNANT L'ACTUAIRE** : `hypotheses`,
`validation_*`, `commentaire` et `statut_rag` sont publiés dans les livrables
(banc `passage_libelles.py`). Ce ne sont pas des défauts latents.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import direction_non_vie.tarification.a3_glm.agent as A3
import direction_non_vie.tarification.a4_ml.agent as A4


class POS_Scorecard_LeCompteEstDERIVE_JamaisEcritEnDur(unittest.TestCase):
    """⚠️ `a3/C9` et `a4/C8` — la légende annonçait un nombre figé."""

    @staticmethod
    def _source(module) -> str:
        import inspect
        return inspect.getsource(module)

    def test_A3_la_scorecard_se_construit_depuis_les_hypotheses_calculees(self):
        """⚠️ La liste était ÉCRITE EN DUR : une hypothèse ajoutée au calcul
        n'apparaissait jamais. `h5_deviance` en était la preuve."""
        src = self._source(A3)
        i = src.index('_LIBELLES_H')
        bloc = src[i:i + 1400]
        self.assertIn('for cle, val in val_glm.items()', bloc,
                      "la scorecard A3 ne derive plus des hypotheses calculees")
        self.assertNotIn('("H1 — Distribution Poisson", val_glm["h1_poisson"]',
                         src, "la liste ecrite en dur est revenue")
        print("    POS-SC A3 la scorecard derive des hypotheses calculees ✅")

    def test_les_deux_legendes_sont_DERIVEES_du_nombre_d_items(self):
        for nom, mod in (('A3', A3), ('A4', A4)):
            with self.subTest(agent=nom):
                src = self._source(mod)
                self.assertIn('{len(items)}', src,
                              f"{nom} : la legende n'est pas derivee de la liste")
                self.assertNotRegex(
                    src, r'"\s*💡\s*3\s*✅',
                    f"{nom} : la legende annonce encore un 3 fige")
        print("    POS-SC les 2 legendes sont derivees de leur liste ✅")

    def test_LE_SECOND_SENS_le_libelle_des_hypotheses_reste_LISIBLE(self):
        """⚠️ Dériver ne doit pas rendre la scorecard illisible : une clé
        technique (`h5_deviance`) affichée telle quelle serait un progrès de
        justesse payé d'une perte pour l'actuaire."""
        src = self._source(A3)
        for cle, libelle in (('h1_poisson', 'H1'), ('h5_deviance', 'H5')):
            with self.subTest(cle=cle):
                self.assertIn(f'"{cle}":', src)
                self.assertIn(libelle, src)
        print("    POS-SC LE SECOND SENS : les libelles restent lisibles ✅")


class POS_Statut_LaDocstringDitCeQueLeCodeFait(unittest.TestCase):
    """⚠️ `a3/C10` et `a4/C9` — deux docstrings qui affirmaient plus."""

    def test_A3_la_docstring_annonce_DEUX_modeles_pas_trois(self):
        doc = A3.AgentA3GLM._calculer_statut_rag.__doc__
        self.assertIn('DEUX', doc,
                      "la docstring annonce encore « les 3 modeles »")
        self.assertIn('a3/C10', doc, "le constat n'est pas trace")
        self.assertNotRegex(doc, r'convergence des 3 mod',
                            "l'affirmation des 3 modeles subsiste")
        print("    POS-ST A3 la docstring dit DEUX modeles ✅")

    def test_A3_le_code_lit_bien_DEUX_metriques_et_pas_le_tweedie(self):
        """⚠️ Le SECOND SENS : la docstring doit décrire le code RÉEL. Si un
        jour le Tweedie entre dans le statut, ce test échoue — et il faudra
        rouvrir `a3/C6` (le Gini Tweedie vaut 0 partout) avant de le laisser
        décider d'un verdict."""
        import inspect
        src = inspect.getsource(A3.AgentA3GLM._calculer_statut_rag)
        self.assertIn("metriques.get('poisson'", src)
        self.assertIn("metriques.get('gamma'", src)
        self.assertNotIn("metriques.get('tweedie'", src,
                         "le Tweedie entre dans le statut : son Gini vaut 0 "
                         "partout (constat a3/C6) — a instruire AVANT")
        print("    POS-ST A3 le code lit deux metriques, pas le Tweedie ✅")

    def test_A4_le_seuil_qui_decide_du_ROUGE_est_NOMME(self):
        """⚠️ Un chiffre qui fait la différence entre AMBRE et ROUGE se nomme,
        sinon personne ne peut le discuter."""
        self.assertTrue(hasattr(A4, 'SEUIL_GINI_ML_EXPLOITABLE'))
        self.assertEqual(A4.SEUIL_GINI_ML_EXPLOITABLE, 0.10)
        import inspect
        src = inspect.getsource(A4.AgentA4ML._calculer_statut_rag)
        self.assertIn('SEUIL_GINI_ML_EXPLOITABLE', src)
        self.assertNotIn('> 0.10', src, "le litteral 0.10 subsiste")
        print("    POS-ST A4 le seuil du ROUGE est nomme ✅")

    def test_A4_la_docstring_porte_la_SECONDE_condition_du_ROUGE(self):
        doc = A4.AgentA4ML._calculer_statut_rag.__doc__
        self.assertIn('SEUIL_GINI_ML_EXPLOITABLE', doc,
                      "la docstring ne nomme pas la seconde condition")
        self.assertIn('a4/C9', doc)
        print("    POS-ST A4 la docstring porte la seconde condition ✅")


class POS_Commentaire_LeDenominateurEstDERIVE(unittest.TestCase):
    """⚠️ `a4/C6` — « 6/8 » : le numérateur était dérivé, le dénominateur inventé."""

    def test_le_denominateur_n_est_plus_un_litteral(self):
        import inspect
        src = inspect.getsource(A4.AgentA4ML._commenter_actuaire_senior)
        self.assertIn('{nb_candidats}', src,
                      "le denominateur n'est pas derive")
        self.assertNotIn('{nb_modeles}/8', src, "le litteral 8 subsiste")
        print("    POS-CO le denominateur est derive, plus un litteral ✅")

    def test_le_nombre_de_candidats_vient_de_la_LISTE_qui_les_porte(self):
        """⚠️ La source unique : `modeles_a_calibrer` est la seule vérité, et
        elle est enregistrée au rapport plutôt que recopiée."""
        import inspect
        src = inspect.getsource(A4.AgentA4ML)
        self.assertIn("rapport['modeles_candidats'] = len(modeles_a_calibrer)",
                      src, "le compte des candidats n'est plus derive de la liste")
        print("    POS-CO le compte des candidats vient de la liste ✅")

    def test_LE_SECOND_SENS_un_repli_existe_si_le_compte_manque(self):
        """⚠️ Un ancien rapport sans `modeles_candidats` ne doit pas casser le
        commentaire — il doit dégrader vers un compte cohérent, jamais vers un
        littéral faux."""
        import inspect
        src = inspect.getsource(A4.AgentA4ML._commenter_actuaire_senior)
        self.assertIn("rapport.get('modeles_candidats') or nb_modeles", src,
                      "aucun repli : un rapport ancien casserait")
        print("    POS-CO LE SECOND SENS : un repli coherent existe ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
