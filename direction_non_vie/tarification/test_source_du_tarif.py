"""
==============================================================================
  LOT D-1 -- LA SOURCE DU TARIF, ET POURQUOI ELLE DEPLACE UN PRIX
==============================================================================

⚠️⚠️ `pipeline_complet` FAIT LUI-MEME LA QUALITE PUIS A2 : son entree est un
portefeuille CLIENT. Deux appelants de production ne lui donnaient pas la meme
chose -- `actuaria_app:3574` la sortie d'A1, `a6_comparaison/agent.py` la
sortie d'A2. **A2 tournait donc deux fois sur le chemin du document signe, et
A2 n'est PAS idempotent.**

MESURE DU 08/09/2026, 3 000 lignes, graine 11
  2 997 contrats sur 3 000 divergeaient de plus d'un centime
  mediane +0,43 EUR | maximum 263,70 EUR | jusqu'a 51,90 % en relatif
  ⚠️⚠️ TOTAL IDENTIQUE A +0,0000 % -- le coefficient d'equilibre ramene les
  deux tarifs a la charge observee. *Aucun controle agrege ne pouvait voir
  cette divergence : elle vit entierement dans la REPARTITION.*

LE DETECTEUR EST PILOTE PAR LE PLAN, sans aucune liste en dur :
`colonnes_produites() - colonnes_sources()` = les colonnes qu'A2 cree et qu'un
fichier client ne contient jamais. Mesure : les 20 plans en portent au moins
une (minimum 3, `mrh`) ; la sortie d'A1 n'en porte aucune.

⚠️ CE QUI N'A PAS ETE FAIT, ET POURQUOI. Rendre A2 idempotent benirait la
double application ; deviner l'etat de l'entree reviendrait a choisir un tarif
a la place de l'appelant. *On refuse, et on dit quoi renommer.*

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
==============================================================================
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys
import unittest

import numpy as np
import pandas as pd

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

from core.plan_tarifaire import PlanTarifaire
from core.qualite_donnees import preambule_qualite
from direction_non_vie.tarification import test_plan_invariants as T
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
)
from direction_non_vie.tarification.pipeline_tarifaire import (
    PortefeuilleDejaTransformeBloquant,
    pipeline_complet,
)

_PLANS = os.path.join(_RACINE, 'plans')
_TMP = os.environ.get('TEMP', '/tmp')


class TestLeDetecteurDeDoubleTransformation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.plan = PlanTarifaire.depuis_yaml(os.path.join(_PLANS, 'auto.yaml'))
        cls.brut = T.portefeuille_auto(1200, 5)
        a2 = AgentA2Preprocessing(models_path=_TMP, audit_path=_TMP,
                                  verbose=False)
        cls.apres_a2 = a2.run(
            {'dataframe': cls.brut, 'branche': cls.plan.lob, 'success': True},
            plan=cls.plan)['dataframe']

    def test_SD1_LE_SCEAU_une_entree_DEJA_transformee_est_REFUSEE(self):
        """⚠️⚠️ LE DEFAUT QUE CE LOT FERME. Le refus NOMME les colonnes : sans
        elles, l'appelant ne sait pas quoi corriger."""
        with self.assertRaises(PortefeuilleDejaTransformeBloquant) as ctx:
            pipeline_complet(self.apres_a2, self.plan)
        message = str(ctx.exception)
        temoins = [c for c in self.plan.colonnes_derivees()
                   if c in self.apres_a2.columns]
        self.assertTrue(temoins, "l'entree de ce controle ne porte aucun "
                                 "temoin : il s'exercerait sur une assiette "
                                 "ou la violation ne peut pas survenir")
        self.assertTrue(any(c in message for c in temoins),
                        f"le refus ne nomme aucune des colonnes {temoins[:3]}")
        print(f"    SD-1 SCEAU : {len(temoins)} temoin(s) vus -> REFUS nomme")

    def test_SD2_LE_MIROIR_un_portefeuille_CLIENT_passe(self):
        """⚠️ Sans ce sens, un detecteur qui refuserait TOUT satisferait SD-1 —
        et plus aucun tarif ne serait jamais ajuste."""
        tarif = pipeline_complet(self.brut, self.plan)
        self.assertIsNotNone(tarif.glm_frequence)
        self.assertGreater(tarif.coefficient_equilibre, 0.0)
        print(f"    SD-2 miroir : portefeuille client ajuste, "
              f"k={tarif.coefficient_equilibre:.6f}")

    def test_SD3_LA_SORTIE_D_A1_passe_elle_aussi(self):
        """⚠️⚠️ C'EST LE SEUL CHEMIN QUE LE DETECTEUR DOIT LAISSER PASSER, et
        `actuaria_app:3574` l'emprunte deja. Un faux positif ici retirerait le
        prix de l'ecran ET du document."""
        r1 = AgentA1Ingestion(audit_path=_TMP, verbose=False).run(
            branche='non_vie', sous_branche='auto',
            dataframe=self.brut, plan=self.plan)
        vus = [c for c in self.plan.colonnes_derivees()
               if c in r1['dataframe'].columns]
        self.assertEqual(vus, [], f"A1 produit des temoins : {vus}")
        pipeline_complet(r1['dataframe'], self.plan)
        print("    SD-3 la sortie d'A1 passe : 0 temoin")

    def test_SD4_AUCUN_des_20_plans_n_est_aveugle_au_detecteur(self):
        """⚠️⚠️ UN PLAN SANS TEMOIN SERAIT UN PLAN OU LE DEFAUT PASSERAIT. Le
        detecteur ne vaut que par l'assiette qu'il couvre."""
        aveugles, mini = [], None
        for fichier in sorted(os.listdir(_PLANS)):
            if not fichier.endswith('.yaml'):
                continue
            p = PlanTarifaire.depuis_yaml(os.path.join(_PLANS, fichier))
            derivees = p.colonnes_derivees()
            if not derivees:
                aveugles.append(fichier)
            mini = len(derivees) if mini is None else min(mini, len(derivees))
        self.assertEqual(aveugles, [],
                         f"plans sans aucun temoin : {aveugles}")
        print(f"    SD-4 les 20 plans portent un temoin (minimum {mini})")

    def test_SD5_les_derivees_ne_sont_JAMAIS_des_colonnes_sources(self):
        """⚠️ Une colonne SOURCE prise pour un temoin ferait refuser tout
        fichier client -- la forme miroir du defaut."""
        for fichier in sorted(os.listdir(_PLANS)):
            if not fichier.endswith('.yaml'):
                continue
            p = PlanTarifaire.depuis_yaml(os.path.join(_PLANS, fichier))
            derivees, sources = set(p.colonnes_derivees()), set(
                p.colonnes_sources())
            self.assertEqual(derivees & sources, set(), fichier)
            self.assertTrue(derivees <= set(p.colonnes_produites()), fichier)
        print("    SD-5 temoins disjoints des sources, inclus dans produites")

    def test_SD6_A2_N_EST_PAS_IDEMPOTENT_c_est_la_raison_du_refus(self):
        """⚠️⚠️ LA MESURE QUI JUSTIFIE TOUT LE LOT. Si A2 etait idempotent, le
        double passage serait inoffensif et ce refus serait du zele. *Une
        propriete, pas un euro : elle survivra aux prochains lots.*"""
        a2 = AgentA2Preprocessing(models_path=_TMP, audit_path=_TMP,
                                  verbose=False)
        deux_fois = a2.run(
            {'dataframe': self.apres_a2, 'branche': self.plan.lob,
             'success': True}, plan=self.plan)['dataframe']
        divergentes = [
            c for c in self.apres_a2.columns
            if pd.api.types.is_numeric_dtype(self.apres_a2[c])
            and pd.api.types.is_numeric_dtype(deux_fois[c])
            and not np.allclose(self.apres_a2[c].to_numpy(dtype=float),
                                deux_fois[c].to_numpy(dtype=float),
                                equal_nan=True)]
        self.assertTrue(
            divergentes,
            "A2 semble idempotent sur cette fixture : la raison d'etre du "
            "refus ne serait plus mesuree ici")
        print(f"    SD-6 A2 non idempotent : {len(divergentes)} colonne(s) "
              f"changent au second passage -- {divergentes[:3]}")

    def test_SD7_la_couche_QUALITE_elle_EST_idempotente(self):
        """⚠️⚠️ LE MOTIF DU CHANTIER APPLIQUE A MON PROPRE CORRECTIF. A6 passe
        desormais par `pipeline_complet(A1)`, qui rejoue la couche qualite. Si
        ELLE n'etait pas idempotente, le correctif reintroduirait la classe de
        defaut qu'il ferme."""
        df = self.brut.copy().reset_index(drop=True)
        df.loc[0:9, self.plan.exposition] = 0.0
        df.loc[10:29, self.plan.exposition] = 1.8
        un = preambule_qualite(df, self.plan).dataframe_propre
        deux = preambule_qualite(un, self.plan).dataframe_propre
        self.assertLess(len(un), len(df),
                        "la couche n'exclut rien : ce controle ne prouverait "
                        "l'idempotence que sur un cas ou elle n'agit pas")
        self.assertEqual(len(deux), len(un))
        self.assertTrue(deux.index.equals(un.index))
        for c in un.columns:
            if pd.api.types.is_numeric_dtype(un[c]):
                self.assertTrue(
                    np.allclose(un[c].to_numpy(dtype=float),
                                deux[c].to_numpy(dtype=float), equal_nan=True),
                    f"la couche qualite change '{c}' au second passage")
        print(f"    SD-7 couche qualite idempotente ({len(df)} -> {len(un)} "
              f"-> {len(deux)})")


class TestLaSourceQueA6EmploiE(unittest.TestCase):

    def test_SD8_LE_SCEAU_A6_batit_le_tarif_depuis_result_a1(self):
        """⚠️⚠️ LE CORRECTIF DOIT ATTEINDRE LA SURFACE. Le garde de
        `pipeline_complet` ne sert a rien si A6 continue de lui remettre la
        sortie d'A2 : le document perdrait simplement son prix. Releve PAR
        AST."""
        a6 = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
              / 'a6_comparaison' / 'agent.py').read_text(encoding='utf-8')
        arbre = ast.parse(a6)
        appels = [n for n in ast.walk(arbre)
                  if isinstance(n, ast.Call)
                  and getattr(n.func, 'id', None) == '_pipeline_complet']
        self.assertTrue(appels, "A6 ne batit plus aucun tarif")
        for appel in appels:
            premier = ast.unparse(appel.args[0]) if appel.args else ''
            self.assertNotIn('result_a2', premier,
                             "A6 batit encore le tarif depuis la sortie d'A2")
            self.assertIn('_source_tarif', premier,
                          "A6 ne batit pas le tarif depuis le portefeuille "
                          "client")
        print("    SD-8 SCEAU : A6 batit le tarif depuis le portefeuille "
              "client")

    def test_SD9_SANS_result_a1_A6_ne_FABRIQUE_pas_de_tarif(self):
        """⚠️⚠️ SE RABATTRE SUR A2 REFABRIQUERAIT LE DEFAUT. L'absence se
        traite comme un refus, jamais comme un repli -- meme doctrine que pour
        les chargements, les taux fiscaux et la decoupe de validation."""
        a6 = (pathlib.Path(_RACINE) / 'direction_non_vie' / 'tarification'
              / 'a6_comparaison' / 'agent.py').read_text(encoding='utf-8')
        arbre = ast.parse(a6)
        source = [n for n in ast.walk(arbre)
                  if isinstance(n, ast.Assign)
                  and any(getattr(c, 'id', None) == '_source_tarif'
                          for c in n.targets)]
        self.assertTrue(source, "`_source_tarif` n'est plus defini")
        texte = ast.unparse(source[0])
        self.assertIn('result_a1', texte)
        self.assertNotIn('result_a2', texte,
                         "A6 se rabat sur la sortie d'A2 quand `result_a1` "
                         "manque : le defaut est refabrique")
        print("    SD-9 sans `result_a1` : aucun repli sur A2")

    def test_SD10_le_pilote_de_gel_remet_bien_result_a1(self):
        """⚠️ Sans cette ligne, le temoin de gel perdrait le prix du document
        sans qu'aucun controle ne rougisse -- la lecon du << tuyau >> du lot 2,
        ou le gel etait reste VERT parce que personne ne fournissait rien."""
        gel = (pathlib.Path(_RACINE) / 'scripts'
               / 'gel_avant_apres.py').read_text(encoding='utf-8')
        arbre = ast.parse(gel)
        appels = [n for n in ast.walk(arbre)
                  if isinstance(n, ast.Call)
                  and getattr(n.func, 'attr', None) == 'run'
                  and 'result_a2' in {k.arg for k in n.keywords}
                  and 'plan' in {k.arg for k in n.keywords}]
        a6 = [n for n in appels
              if 'result_a4' in {k.arg for k in n.keywords}]
        self.assertTrue(a6, "l'appel a A6 est introuvable dans le pilote")
        for appel in a6:
            self.assertIn('result_a1', {k.arg for k in appel.keywords},
                          "le pilote de gel ne remet pas le portefeuille "
                          "client a A6 : le document perdrait son prix")
        print("    SD-10 le pilote de gel remet `result_a1` a A6")


if __name__ == '__main__':
    unittest.main(verbosity=2)
