"""CONTRÔLES POSITIFS DU LOT 1.2 — `core/plan_tarifaire.py`.

Trois constats de l'audit d'août 2026, et **une seule et même cause** :
*le plan validait la COHÉRENCE des combinaisons, jamais l'APPARTENANCE des
valeurs* — et ses garde-fous regardaient une LISTE de noms au lieu d'une
PROPRIÉTÉ.

  `plan/C1` — la garde de l'exposition contournée par les INTERACTIONS.
              Mesuré jusqu'à la prime : rapport 1,8339 au lieu de 2,0000
              quand l'exposition double, soit **−8,3 %**.
  `plan/C2` — la CIBLE déclarable comme facteur, sans aucune garde.
  `plan/C3` — un `type` ou un `encodage` mal orthographié fait disparaître le
              facteur EN SILENCE, et `verifier_completude_plan` annonce
              `ampute=False`.

⚠️⚠️ CHAQUE CONTRÔLE SE MESURE DANS LES DEUX SENS. Ce qui doit être REFUSÉ, et
ce qui ne doit JAMAIS être cassé. Le second sens est celui qui manquait au
dépôt et qui a produit les bloquants B5, B7 et B9 : un garde-fou qui refuse
tout passe le premier sens sans rien protéger.
"""
import os
import pathlib
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.plan_tarifaire import Facteur, PlanTarifaire

RACINE = pathlib.Path(__file__).resolve().parent.parent
PLANS = RACINE / 'plans'

_BASE = {'lob': 'ctrl', 'exposition': 'expo', 'cible_frequence': 'nb',
         'cible_cout': 'cout'}
_AGE = Facteur('age', 'continu')


class POS_Plan_C1_LExpositionNEntrePasParUneInteraction(unittest.TestCase):
    """⚠️ `plan/C1` — LA GARDE REGARDAIT UNE LISTE, PAS UNE PROPRIÉTÉ.

    La spec (`plan_execution_6_actions.md` l.294) demandait : « *`exposition` et
    `log_exposition` ne doivent jamais figurer dans `colonnes_produites()`* ».
    Le code faisait EXACTEMENT cela — et une interaction produit
    `inter_age_expo`, qui n'est ni `expo` ni `log_expo`.

    **Le garde-fou était exact sur les formes prévues et muet sur les autres.**
    """

    def test_l_interaction_avec_l_exposition_est_refusee(self):
        for a, b in (('age', 'expo'), ('expo', 'age')):
            with self.subTest(interaction=f"{a} x {b}"):
                with self.assertRaises(ValueError) as ctx:
                    PlanTarifaire(**_BASE, facteurs=(_AGE,),
                                  interactions=((a, b),))
                self.assertIn("interaction", str(ctx.exception),
                              "le message ne nomme pas la SURFACE fautive")
        print("    POS-1.2a interaction avec l'exposition : REFUSEE (2 ordres) ✅")

    def test_les_trois_surfaces_sont_gardees(self):
        """⚠️ « SUR QUELLE ASSIETTE ? » — un rôle fixe peut entrer par trois
        portes, et une garde qui n'en ferme qu'une n'en ferme aucune."""
        portes = {
            'nom source (one_hot)': lambda: PlanTarifaire(
                **_BASE, facteurs=(_AGE, Facteur(
                    'expo', 'categoriel', encodage='one_hot',
                    modalites=('court', 'long'), reference='court'))),
            'operande d interaction': lambda: PlanTarifaire(
                **_BASE, facteurs=(_AGE,), interactions=(('age', 'expo'),)),
            'colonne produite': lambda: PlanTarifaire(
                **_BASE, facteurs=(_AGE, Facteur('expo', 'continu'))),
        }
        for porte, fabrique in portes.items():
            with self.subTest(porte=porte), self.assertRaises(ValueError):
                fabrique()
        print(f"    POS-1.2a les {len(portes)} surfaces sont gardees ✅")

    def test_une_interaction_LEGITIME_n_est_PAS_cassee(self):
        """⚠️ LE SECOND SENS. `auto.yaml` déclare `age × bonus_malus` — une
        garde qui refuserait toute interaction passerait le premier test sans
        rien protéger, et détruirait un plan de production."""
        p = PlanTarifaire(**_BASE,
                          facteurs=(_AGE, Facteur('bonus_malus', 'continu')),
                          interactions=(('age', 'bonus_malus'),))
        self.assertIn('inter_age_bonus_malus', p.colonnes_produites())
        print("    POS-1.2a interaction legitime PRESERVEE ✅")


class POS_Plan_C2_LaCibleNEstPasUnFacteur(unittest.TestCase):
    """⚠️ `plan/C2` — AUCUNE GARDE NE PROTÉGEAIT LES CIBLES.

    L'exposition en avait une, les cibles non. Ce qui les arrêtait ensuite
    dépendait du NOMBRE d'arguments que l'appelant avait passés : A3 et
    `pipeline_tarifaire` passent les deux cibles (chacune dénonce l'autre),
    **A4, A5 et A6 n'en passent qu'une** (`col_cible: str`). La protection
    n'existait donc pas pour trois agents sur six.

    ⚠️ POURQUOI C'EST LA MÊME PROPRIÉTÉ QUE B9, et non un jugement de méthode :
    `exposition` entre comme OFFSET, `cible_frequence` comme RÉPONSE du modèle
    de fréquence et comme POIDS du modèle de coût moyen, `cible_cout` comme
    RÉPONSE. **Les trois entrent avec un rôle FIXE.** Les refuser comme
    facteurs libres, c'est refuser de prédire une grandeur par elle-même — pas
    d'arbitrer un choix de modélisation. La sinistralité passée LÉGITIME est
    une autre colonne, observée sur une autre période, et le plan la porte
    déjà : `anteriorite=True` (critère V14).
    """

    def test_les_deux_cibles_sont_refusees_comme_facteurs(self):
        for cible in ('nb', 'cout'):
            with self.subTest(cible=cible):
                with self.assertRaises(ValueError) as ctx:
                    PlanTarifaire(**_BASE,
                                  facteurs=(_AGE, Facteur(cible, 'continu')))
                self.assertIn("cible", str(ctx.exception).lower())
        print("    POS-1.2b les deux cibles refusees comme facteurs ✅")

    def test_la_cible_est_refusee_AUSSI_dans_une_interaction(self):
        """La même porte que C1 : sans ce sens, `age × nb` rentrerait."""
        with self.assertRaises(ValueError) as ctx:
            PlanTarifaire(**_BASE, facteurs=(_AGE,),
                          interactions=(('age', 'nb'),))
        self.assertIn("interaction", str(ctx.exception))
        print("    POS-1.2b la cible dans une interaction : REFUSEE ✅")

    def test_l_anteriorite_LEGITIME_n_est_PAS_cassee(self):
        """⚠️ LE SECOND SENS, et il compte : le BLOQUANT B5 a coûté −17,4 % de
        Gini pour UN facteur d'antériorité détruit. Une garde trop large sur
        « ce qui ressemble à de la sinistralité » referait ce dégât."""
        p = PlanTarifaire(**_BASE, facteurs=(
            _AGE, Facteur('antecedents_sinistres_3ans', 'continu',
                          anteriorite=True)))
        self.assertIn('antecedents_sinistres_3ans', p.colonnes_produites())
        print("    POS-1.2b anteriorite legitime PRESERVEE ✅")


class POS_Plan_C3_UneValeurInconnueNeSeTaitPas(unittest.TestCase):
    """⚠️ `plan/C3` — `Literal` N'EST PAS APPLIQUÉ À L'EXÉCUTION.

    `type="ordinal"` et `encodage="onehot"` étaient acceptés sans un mot, et
    `colonnes_produites()` rendait alors `()` : le facteur, présent dans les
    données et déclaré au plan, n'atteignait AUCUN modèle.

    ⚠️⚠️ ET LE DÉTECTEUR D'AMPUTATION EST STRUCTURELLEMENT AVEUGLE À CETTE
    PERTE : `verifier_completude_plan` compare `colonnes_produites()` aux
    données — or le facteur perdu n'est justement plus dans
    `colonnes_produites()`. Il annonçait `ampute=False`.
    """

    def test_un_type_ou_un_encodage_inconnu_est_refuse(self):
        cas = {
            "type 'ordinal'": lambda: Facteur('bm', 'ordinal'),
            "encodage 'onehot'": lambda: Facteur(
                'region', 'categoriel', encodage='onehot', modalites=('a', 'b')),
            "transformation 'sqrt'": lambda: Facteur(
                'age', 'continu', transformation='sqrt'),
        }
        for libelle, fabrique in cas.items():
            with self.subTest(cas=libelle):
                with self.assertRaises(ValueError) as ctx:
                    fabrique()
                self.assertIn("inconnu", str(ctx.exception))
        print(f"    POS-1.2c les {len(cas)} valeurs inconnues sont refusees ✅")

    def test_le_binaire_n_accepte_plus_un_encodage_IGNORE(self):
        """Mesuré avant : `binaire + one_hot + modalites` → `('x',)`.
        L'actuaire signait un one-hot et obtenait autre chose."""
        with self.assertRaises(ValueError) as ctx:
            Facteur('x', 'binaire', encodage='one_hot', modalites=('a', 'b'))
        self.assertIn("IGNORE", str(ctx.exception))
        print("    POS-1.2c binaire + encodage : REFUSE (il serait ignore) ✅")

    def test_LE_FILET_un_facteur_qui_ne_produit_rien_est_refuse(self):
        """⚠️⚠️ LE FILET ATTRAPE CE QUE LES CONTRÔLES NOMMÉS NE VOIENT PAS.

        Un one-hot à modalité unique égale à la référence ne produit aucune
        colonne, et **aucun contrôle nommé ne le refuse** — ce cas n'est dans
        aucun des trois constats. C'est la propriété qui le prend : *un facteur
        déclaré qui ne produit rien est un défaut, quelle qu'en soit la cause.*
        """
        with self.assertRaises(ValueError) as ctx:
            Facteur('r', 'categoriel', encodage='one_hot',
                    modalites=('a',), reference='a')
        self.assertIn("AUCUNE", str(ctx.exception))
        print("    POS-1.2c filet : un facteur sans colonne est REFUSE ✅")

    def test_les_declarations_LEGITIMES_ne_sont_PAS_cassees(self):
        """⚠️ LE SECOND SENS : les trois formes que le dépôt utilise vraiment."""
        attendus = {
            'continu': (Facteur('age', 'continu'), ('age',)),
            'continu + log': (Facteur('age', 'continu', transformation='log'),
                              ('age', 'log_age')),
            'one_hot 3 modalites': (
                Facteur('region', 'categoriel', encodage='one_hot',
                        modalites=('a', 'b', 'c'), reference='a'),
                ('region_b', 'region_c')),
        }
        for libelle, (f, cols) in attendus.items():
            with self.subTest(cas=libelle):
                self.assertEqual(f.colonnes_produites(), cols)
        print(f"    POS-1.2c les {len(attendus)} formes legitimes PRESERVEES ✅")


class POS_Plan_LesVingtPlansDuDepotChargent(unittest.TestCase):
    """⚠️⚠️ LE CONTRÔLE QUI COMPTE LE PLUS — « ce qu'il ne doit JAMAIS casser ».

    `depuis_yaml` a **20 appelants de production**, dont l'application. Une
    garde trop stricte n'échoue pas discrètement : elle arrête toute la chaîne
    au chargement du plan. Ce test est la contrepartie obligatoire des trois
    classes ci-dessus.
    """

    def test_les_plans_du_depot_chargent_tous(self):
        fichiers = sorted(PLANS.glob('*.yaml'))
        self.assertGreaterEqual(len(fichiers), 20,
                                f"{len(fichiers)} plans trouves dans {PLANS}")
        echecs = []
        for p in fichiers:
            try:
                PlanTarifaire.depuis_yaml(p)
            except Exception as e:  # noqa: BLE001 — on rapporte, on ne masque pas
                echecs.append(f"{p.name}: {type(e).__name__}: {e}")
        self.assertEqual(
            echecs, [],
            "des plans de PRODUCTION sont refuses par les gardes du lot 1.2 :\n"
            + "\n".join(echecs))
        print(f"    POS-1.2d les {len(fichiers)} plans du depot chargent ✅")


if __name__ == '__main__':
    unittest.main(verbosity=2)
