"""CONTRÔLES POSITIFS — une hypothèse NON TESTÉE ne rend pas VERT.

⚠️⚠️ CE LOT A COMMENCÉ PAR UNE CORRECTION DE MON PROPRE CLASSEMENT.
Sur les cinq constats visés, **quatre étaient déjà fermés** — corrigés dans le
code, jamais reportés dans les relevés. Je les avais classés « vivants » sur la
foi de ce que le relevé DISAIT, sans re-mesurer le code. *L'archive prévient
elle-même : « ils mesurent l'état ACTUEL, pas celui du jour de l'audit — lire
le chiffre, pas l'étiquette ». J'ai lu l'étiquette.*

Ces contrôles épinglent donc **ce qui est déjà acquis**, pour qu'il ne
régresse pas :

  `a3/C2` — H1 sans colonne de fréquence rendait VERT sur `ratio=1.30` codé en
            dur. Mesuré : **AMBRE**, « Sur-dispersion NON mesurée ».
  `a3/C3` — H4 « non testée » valait VERT. Mesuré : **AMBRE**.
  `a3/C8` — la docstring annonçait trois bandes, le code en applique quatre, et
            `0.12` sortait VERT. Mesuré : **`0.12 → AMBRE`**.
  `a4/C4` — `validation_ml` et `hypotheses` divergeaient dans le même retour.
            Mesuré : **identiques sur toutes les clés**.

Et un seul restait vivant, corrigé ici :

  `a5/C1` — `max(gini_cann, gini_tabnet, **0**)` publiait « Gini DL = 0.0000 »
            là où la mesure valait **−0,1083**. *Un zéro qui signifie « écrêté »
            est indiscernable d'un zéro mesuré* — même famille qu'`a3/C6`.
            ⚠️ **Le VERDICT ne change pas** (ROUGE dans les deux cas) ; **le
            NOMBRE publié change**. Les deux se déclarent séparément.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import numpy as np
import pandas as pd

from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM


def _sans_frequence():
    """Un `df_train` où AUCUNE colonne de fréquence n'est exploitable."""
    return pd.DataFrame({'age': np.arange(100.0)})


class POS_Hyp_UneHypotheseNonTesteeNeRendPasVERT(unittest.TestCase):
    """⚠️ `a3/C2` et `a3/C3` — déjà fermés ; ces contrôles les épinglent."""

    @classmethod
    def setUpClass(cls):
        cls.agent = AgentA3GLM(audit_path='/tmp', verbose=False)
        cls.val = cls.agent._valider_hypotheses_glm(
            df_train=_sans_frequence(), predictions={}, metriques={})

    def test_a3C2_H1_sans_donnee_rend_AMBRE_et_le_DIT(self):
        h1 = self.val['h1_poisson']
        self.assertEqual(h1['statut'], 'AMBRE',
                         "H1 rend VERT sur une hypothese NON MESUREE")
        self.assertIn('NON mesurée', h1['message'],
                      "le message ne dit pas que la mesure n'a pas eu lieu")
        self.assertIsNone(h1['ratio_disp'],
                          "un chiffre est publie alors que rien n'a ete calcule")
        print("    POS-HYP a3/C2 H1 non mesuree -> AMBRE, et le dit ✅")

    def test_a3C3_H4_non_testee_rend_AMBRE_et_le_DIT(self):
        h4 = self.val['h4_stabilite']
        self.assertEqual(h4['statut'], 'AMBRE',
                         "H4 « non testee » rend VERT")
        self.assertIn('NON testée', h4['message'])
        self.assertIsNone(h4['cv_max'],
                          "un CV est publie pour un bootstrap jamais lance")
        print("    POS-HYP a3/C3 H4 non testee -> AMBRE, et le dit ✅")

    def test_LE_SECOND_SENS_une_hypothese_MESUREE_peut_encore_rendre_VERT(self):
        """⚠️⚠️ SANS LUI, UN STATUT FIGÉ À `AMBRE` PASSERAIT LES DEUX TESTS
        CI-DESSUS. Une hypothèse réellement vérifiée doit encore pouvoir être
        déclarée satisfaite — sinon le garde-fou ne surveille plus, il refuse."""
        rng = np.random.default_rng(0)
        df = pd.DataFrame({'nb_sinistres': rng.poisson(0.2, 500).astype(float)})
        v = self.agent._valider_hypotheses_glm(
            df_train=df, predictions={}, metriques={})
        h1 = v['h1_poisson']
        self.assertEqual(h1['statut'], 'VERT',
                         f"une hypothese MESUREE et satisfaite ne rend plus "
                         f"VERT : {h1['message']}")
        self.assertIsNotNone(h1['ratio_disp'])
        print("    POS-HYP LE SECOND SENS : une hypothese mesuree rend VERT ✅")

    def test_a3C8_les_QUATRE_bandes_de_H3_sont_celles_appliquees(self):
        """⚠️ La docstring annonçait TROIS bandes, le code en applique quatre,
        et `0.12` sortait VERT. Chaque borne est épinglée."""
        attendu = {0.07: 'ROUGE', 0.09: 'AMBRE', 0.12: 'AMBRE',
                   0.16: 'VERT', 0.30: 'VERT'}
        for gini, statut in attendu.items():
            with self.subTest(gini=gini):
                v = self.agent._valider_hypotheses_glm(
                    df_train=_sans_frequence(), predictions={},
                    metriques={'poisson': {'gini': gini}})
                self.assertEqual(v['h3_ajustement']['statut'], statut,
                                 f"Gini {gini} ne rend plus {statut}")
        print(f"    POS-HYP a3/C8 les {len(attendu)} bornes de H3 sont tenues ✅")


class POS_Hyp_a5C1_UnGiniECRETENEstPasUnGiniMESURE(unittest.TestCase):
    """⚠️ `a5/C1` — la part vivante : `max(..., 0)` publiait un faux zéro.

    ⚠️⚠️ CE QUI CHANGE ET CE QUI NE CHANGE PAS, déclaré séparément :
      · le **VERDICT** est identique — ROUGE avant, ROUGE après ;
      · le **NOMBRE PUBLIÉ** change — « Gini DL = 0.0000 » devenait un chiffre
        qu'aucun modèle n'avait atteint, il vaut désormais la mesure réelle.
    *Un zéro qui signifie « écrêté » est indiscernable d'un zéro mesuré.*
    """

    def test_le_plancher_a_zero_a_disparu_du_calcul(self):
        import inspect

        from direction_non_vie.tarification.a5_deep_learning import agent as A5
        src = inspect.getsource(A5.AgentA5DeepLearning)
        self.assertNotIn('max(gini_cann, gini_tabnet, 0)', src,
                         "le plancher a zero subsiste : un Gini negatif serait "
                         "encore publie comme 0.0000")
        self.assertIn('max(gini_cann, gini_tabnet)', src)
        print("    POS-HYP a5/C1 le plancher a zero a disparu ✅")

    def test_un_gini_NEGATIF_est_publie_tel_quel(self):
        """⚠️ Un Gini négatif est une INFORMATION — il dit que le modèle classe
        à l'envers. L'écrêter à 0 le fait passer pour « sans pouvoir
        discriminant », ce qui est plus flatteur que la réalité."""
        import inspect

        from direction_non_vie.tarification.a5_deep_learning import agent as A5
        src = inspect.getsource(A5.AgentA5DeepLearning)
        i = src.index('gini_dl_max  = max(gini_cann, gini_tabnet)')
        bloc = src[max(0, i - 900):i]
        self.assertIn('a5/C1', bloc, "le constat n'est pas trace au code")
        self.assertIn('indiscernable', bloc,
                      "la raison du correctif n'est pas ecrite")
        print("    POS-HYP a5/C1 un Gini negatif se publie tel quel ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
