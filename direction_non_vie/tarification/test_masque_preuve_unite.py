"""⚠️⚠️ UN SIGNAL QUI DÉSIGNE TOUT LE MONDE NE DÉSIGNE PERSONNE.

Étape ② du chantier 1-B, décidée par Selasse le 01/09/2026.

`unite_exposition_contredite` sortait avec `np.ones(len(df))` : **toutes** les
lignes. Mesuré sur 20 000 contrats dont **une seule** à 1,02 an — 0,0050 % :

```
  AVANT : signal 20 000 l. = 100,0000 %  ->  escalade  ->  BLOQUE
  APRES : signal      1 l. =   0,0050 %  ->  signale, rien de bloque
```

> *Une ligne d'arrondi refusait le tarif de vingt mille contrats, et elle le
> refusait par l'imprécision du signal, pas par la gravité du fait.*

⚠️⚠️ ET L'ASSIETTE EST ASYMÉTRIQUE, POUR UNE RAISON QUI SE MESURE. La
contradiction se lit dans deux sens, et **la preuve n'a pas la même forme** :

  · **donnée TROP GRANDE** (`annee` déclarée, max 1,02) — les lignes au-dessus
    de la borne sont la preuve, et elles seules ;
  · **donnée TROP PETITE** (`mois` déclarée, max 0,9) — **aucune** ligne ne
    dépasse la borne de 12 : la preuve est que TOUTES sont petites.

*Restreindre les deux sens aurait fait DISPARAÎTRE le second signal* —
`_ajouter` ignore un masque vide, et une déclaration `mois` fausse serait
redevenue muette, exactement le décor que `UX-12` existe pour empêcher. `MP-3`
tient cette moitié-là.

⚠️ AUCUN EURO, ET C'EST MESURÉ DEUX FOIS (`MP-5`) : la règle 3 n'écrit nulle
part, et le dataframe produit sans signature après le correctif est
**identique, ligne à ligne**, à celui que l'ancien code produisait après
signature nominative. *Ce que le correctif retire est une SIGNATURE, pas une
correction.*
"""
import ast
import dataclasses
import inspect
import pathlib
import unittest

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire
from core.qualite_donnees import borne_exposition, controler_qualite

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_PLAN = PlanTarifaire.depuis_yaml(str(_RACINE / 'plans' / 'auto.yaml'))
_E, _F, _C = _PLAN.exposition, _PLAN.cible_frequence, _PLAN.cible_cout


def _cadre(n, seed, expo=None):
    """n lignes distinctes et cohérentes : seule l'exposition est en cause."""
    rng = np.random.default_rng(seed)
    nb = rng.integers(0, 3, n).astype(float)
    cout = np.where(nb > 0, rng.uniform(500, 5000, n).round(2), 0.0)
    return pd.DataFrame({
        _E: np.ones(n) if expo is None else expo, _F: nb, _C: cout,
        'prime_acquise': (200 + np.arange(n) * 0.01).round(2)})


def _signal(rapport):
    for a in (rapport.signalements or []):
        if a.code == 'unite_exposition_contredite':
            return a
    return None


def _bloc_regle_3():
    """Le bloc `if` de la règle 3, par AST — jamais au texte.

    ⚠️ *Une citation n'est pas une affirmation* : ce fichier CITE `np.ones`
    dans sa propre docstring pour raconter le défaut. L'assiette est le code.
    """
    src = inspect.getsource(controler_qualite).lstrip()
    for n in ast.walk(ast.parse(src)):
        if (isinstance(n, ast.If)
                and 'unite_exposition_contredite' in ast.unparse(n)):
            return n
    raise AssertionError('bloc de la règle 3 introuvable')


class TestMasquePreuveUnite(unittest.TestCase):

    def test_MP_1_une_ligne_ne_bloque_plus_vingt_mille_contrats(self):
        """⚠️⚠️ LE CONSTAT LUI-MÊME, DANS LES CHIFFRES DE SELASSE."""
        n = 20_000
        df = _cadre(n, 7)
        df.loc[0, _E] = 1.02
        self.assertEqual(int((df[_E] > 1).sum()), 1, 'le témoin a dérivé')

        rapport = controler_qualite(df.copy(), _PLAN)
        signal = _signal(rapport)

        self.assertIsNotNone(signal, "la contradiction n'est plus signalée")
        self.assertEqual(
            signal.nb_lignes, 1,
            f"le signal porte {signal.nb_lignes} lignes pour UNE ligne "
            f"fautive : il escalade sur sa propre imprécision.")
        self.assertLess(signal.proportion, 0.05)
        self.assertFalse(
            rapport.bloque,
            "une ligne d'arrondi refuse encore le tarif de 20 000 contrats")
        self.assertIsNotNone(rapport.dataframe_propre)
        print(f"    OK MP-1 1 ligne sur {n} -> signal {signal.nb_lignes} l. "
              f"= {signal.proportion:.4%}, plus aucun blocage")

    def test_MP_2_le_masque_est_EXACTEMENT_les_lignes_au_dessus_de_la_borne(
            self):
        """⚠️ Le signal doit NOMMER les lignes, pas seulement en compter le bon
        nombre. *Un compte juste sur les mauvaises lignes reste faux.*"""
        n = 5_000
        df = _cadre(n, 11)
        attendues = {3, 17, 1234, 4999}
        for i in attendues:
            df.loc[i, _E] = 1.5

        signal = _signal(controler_qualite(df.copy(), _PLAN))
        self.assertIsNotNone(signal)
        self.assertEqual(
            set(signal.index), attendues,
            "le masque ne désigne pas les lignes qui portent la preuve")
        print(f"    OK MP-2 masque = {sorted(attendues)}, exactement les "
              f"lignes au-dessus de la borne {borne_exposition(_PLAN):g}")

    def test_MP_3_le_sens_TROP_PETIT_reste_total_et_BLOQUANT(self):
        """⚠️⚠️ LA MOITIÉ QUE LE CORRECTIF AURAIT PU DÉTRUIRE EN SILENCE.

        `mois` déclarée sur une donnée annuelle : **aucune** ligne ne dépasse
        la borne de 12. Un masque « lignes au-dessus de la borne » serait VIDE,
        `_ajouter` l'ignorerait, et le signal disparaîtrait — la déclaration
        fausse redeviendrait muette. Ici la preuve EST que toutes sont petites.
        """
        plan_mois = dataclasses.replace(_PLAN, unite_exposition='mois')
        n = 400
        df = _cadre(n, 3)
        self.assertEqual(
            int((df[_E] > borne_exposition(plan_mois)).sum()), 0,
            "le témoin porte des lignes au-dessus de 12 : il ne mesure plus "
            "le sens TROP PETIT")

        rapport = controler_qualite(df.copy(), plan_mois)
        signal = _signal(rapport)
        self.assertIsNotNone(
            signal,
            "une déclaration `mois` fausse est redevenue MUETTE : le "
            "correctif du sens TROP GRAND a détruit l'autre moitié.")
        self.assertEqual(signal.nb_lignes, n)
        self.assertTrue(
            rapport.bloque,
            "une unité fausse mésestime TOUT le portefeuille : elle doit "
            "escalader (`UX-12`)")
        print(f"    OK MP-3 sens TROP PETIT : {signal.nb_lignes}/{n} = "
              f"100 %, bloquant -- l'autre moitie est intacte")

    def test_MP_4_le_VRAI_defaut_d_unite_bloque_toujours(self):
        """⚠️⚠️ LE CONTRÔLE QUI EMPÊCHE QUE `MP-1` NE DEVIENNE UNE PASSOIRE.

        Une donnée réellement mensuelle sous un plan `annee` : la quasi-totalité
        des lignes dépasse la borne. Le masque précis les désigne toutes, et le
        fichier bloque. *Si le correctif avait rendu ce cas passant, il aurait
        échangé un faux blocage contre un vrai silence.*
        """
        n = 20_000
        rng = np.random.default_rng(9)
        df = _cadre(n, 9, expo=rng.uniform(1.5, 11, n).round(2))
        rapport = controler_qualite(df.copy(), _PLAN)
        signal = _signal(rapport)
        self.assertIsNotNone(signal)
        self.assertGreater(signal.proportion, 0.05)
        self.assertTrue(rapport.bloque,
                        "une donnée mensuelle sous un plan annuel ne bloque "
                        "plus : le signal est devenu décoratif")
        print(f"    OK MP-4 vraie donnee mensuelle : "
              f"{signal.nb_lignes}/{n} = {signal.proportion:.2%}, BLOQUE")

    def test_MP_5_aucun_euro_le_correctif_retire_une_SIGNATURE(self):
        """⚠️⚠️ « AUCUN EURO » SE PROUVE DEUX FOIS, IL NE SE DÉCLARE PAS.

        ① la règle 3 n'écrit nulle part — vérifié par AST sur les CIBLES
        d'affectation, pas sur le texte du bloc (`df[col]` en lecture n'est pas
        une écriture, et mon premier contrôle s'y était trompé) ;
        ② le dataframe produit SANS signature après le correctif est identique,
        ligne à ligne, à celui produit AVEC signature — c'est-à-dire au
        résultat que l'ancien code donnait une fois l'actuaire nommé.
        """
        bloc = _bloc_regle_3()
        ecritures = [
            ast.unparse(t)
            for n in ast.walk(bloc)
            if isinstance(n, (ast.Assign, ast.AugAssign))
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
            if isinstance(t, (ast.Subscript, ast.Attribute))]
        self.assertEqual(ecritures, [],
                         f'la règle 3 écrit : {ecritures}')
        mutantes = {'drop', 'fillna', 'replace', 'clip', 'assign', 'update'}
        appelees = {n.func.attr for n in ast.walk(bloc)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)}
        self.assertEqual(mutantes & appelees, set(),
                         f'la règle 3 mute : {mutantes & appelees}')

        n = 20_000
        df = _cadre(n, 7)
        df.loc[0, _E] = 1.02
        sans = controler_qualite(df.copy(), _PLAN)
        avec = controler_qualite(df.copy(), _PLAN,
                                 qualite_validee_par='temoin')
        self.assertTrue(
            sans.dataframe_propre.equals(avec.dataframe_propre),
            "le correctif produit un dataframe DIFFERENT de celui obtenu "
            "apres signature : il ne retire pas une signature, il deplace "
            "quelque chose.")
        self.assertEqual(float(sans.dataframe_propre.loc[0, _E]), 1.0,
                         "la ligne à 1,02 n'est plus plafonnée par la règle 2")
        print(f"    OK MP-5 0 ecriture, 0 mutation ; {n} lignes identiques "
              f"sans signature et avec -- une SIGNATURE retiree, rien d autre")

    def test_MP_6_second_sens_une_unite_JUSTE_ne_declenche_toujours_RIEN(self):
        """⚠️ Un signal qui tirerait sur une déclaration juste serait du bruit,
        et l'actuaire cesserait de le lire — dans les DEUX sens."""
        self.assertIsNone(_signal(controler_qualite(_cadre(400, 3), _PLAN)),
                          "donnée annuelle + plan `annee` : signal parasite")
        plan_mois = dataclasses.replace(_PLAN, unite_exposition='mois')
        rng = np.random.default_rng(5)
        en_mois = _cadre(400, 5, expo=rng.uniform(1, 11, 400).round(2))
        self.assertIsNone(_signal(controler_qualite(en_mois, plan_mois)),
                          "donnée en mois + plan `mois` : signal parasite")
        print("    OK MP-6 second sens : aucune declaration juste ne "
              "declenche, dans les deux sens")

    def test_MP_7_le_texte_publie_DIT_sur_quoi_il_porte(self):
        """⚠️ Le rapport signé porte le compte de lignes. Passer de 20 000 à 1
        sans dire POURQUOI laisserait croire à une perte de détection.

        *Le texte qui accompagne un comportement se relit quand il change.*
        """
        n = 5_000
        df = _cadre(n, 11)
        df.loc[3, _E] = 1.5
        grand = _signal(controler_qualite(df.copy(), _PLAN))
        self.assertIn('au-dessus de la borne', grand.description)
        self.assertIn('elles seules', grand.description)

        plan_mois = dataclasses.replace(_PLAN, unite_exposition='mois')
        petit = _signal(controler_qualite(_cadre(400, 3), plan_mois))
        self.assertIn('TOUTES les lignes', petit.description)
        self.assertIn('aucune ne depasse', petit.description)
        self.assertNotEqual(grand.description, petit.description)
        print("    OK MP-7 les deux sens publient une assiette DIFFERENTE, "
              "et chacune dit laquelle")


if __name__ == '__main__':
    unittest.main(verbosity=2)
