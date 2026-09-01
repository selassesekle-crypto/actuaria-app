"""⚠️⚠️ UNE PHRASE DE PORTÉE SE MESURE COMME UN CHIFFRE.

Étape ① du chantier 1-B, décidée par Selasse le 01/09/2026.

`core/qualite_donnees.py` a affirmé **« Aucun des 20 plans ne déclare
d'unité »** de l'étape 2 du chantier `unite_exposition` jusqu'au 01/09. L'étape
5 du **même chantier** a fait déclarer `annee` aux vingt plans.

> *La phrase a survécu quatre jours à sa propre mesure — et c'est elle qui
> justifiait « aucun euro ne bouge sur l'existant ».*

⚠️ LA CONCLUSION TENAIT, LA JUSTIFICATION NON. `borne_exposition('annee')` vaut
1,0, exactement `PLAFOND_EXPOSITION` : aucun euro n'a bougé. Mais il tenait
pour une raison que la phrase ne disait plus — et **la règle 3 est devenue
VIVANTE en production sans que le commentaire le dise**.

⚠️⚠️ LE REMÈDE N'EST PAS DE RÉÉCRIRE LA PHRASE, C'EST DE LA DÉRIVER. Le patron
existe déjà deux fois dans le dépôt : `A3-8` et `A4-3` re-vérifient leur
mesure à chaque gate **« au lieu de recopier cette mesure »**. Ici, rien ne le
faisait.

⚠️ SECOND DÉFAUT DE LA MÊME FAMILLE, TROUVÉ EN TRAÇANT : la feuille de route
affirmait que le chemin agent tarifie sur **60 lignes** à fréquence ou coût
négatifs. `qualite/C8`, fermé le 31/08 **après** cette mesure, a sorti le coût
de la règle 1 : il est SIGNALÉ et GARDÉ par les deux chemins. Le delta réel de
1-B est de **30 lignes**. `PM-3` le dérive par exécution.
"""
import inspect
import pathlib
import re
import unittest

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire
from core.qualite_donnees import (
    PLAFOND_EXPOSITION,
    borne_exposition,
    controler_qualite,
)

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_PLANS = sorted((_RACINE / 'plans').glob('*.yaml'))


def _charges():
    return [PlanTarifaire.depuis_yaml(str(p)) for p in _PLANS]


def _commentaires(fonction):
    """Les COMMENTAIRES du corps d'une fonction, docstring exclue.

    ⚠️ *Une citation n'est pas une affirmation* : on lit ce que le code
    COMMENTE, pas la prose d'un test qui cite le defaut.
    """
    src = inspect.getsource(fonction)
    return '\n'.join(l.strip() for l in src.splitlines()
                     if l.strip().startswith('#'))


class TestPorteeMesuree(unittest.TestCase):

    def test_PM_1_la_declaration_d_unite_se_derive_des_plans_reels(self):
        """⚠️⚠️ LE CONTRÔLE QUI MANQUAIT — il aurait tiré le jour de l'étape 5.

        Le commentaire de `controler_qualite` affirme un compte. Ce compte se
        DÉRIVE ici des vingt fichiers de plan, jamais recopié.
        """
        plans = _charges()
        self.assertEqual(len(plans), 20, 'le corpus de plans a change')
        declarants = [p for p in plans
                      if getattr(p, 'unite_exposition', None) is not None]
        n = len(declarants)

        commentaire = _commentaires(controler_qualite)
        self.assertIn(
            'les 20 plans déclarent', commentaire,
            "le commentaire de `controler_qualite` ne dit plus ce que les "
            "plans font")
        self.assertEqual(
            n, 20,
            f"{n}/20 plans déclarent `unite_exposition`, mais le commentaire "
            f"de `controler_qualite` en affirme 20. *Corriger la phrase et "
            f"non le contrôle, c'est refaire exactement le défaut du 01/09.*")
        unites = {p.unite_exposition for p in declarants}
        self.assertEqual(
            unites, {'annee'},
            f"le commentaire nomme `annee` ; les plans déclarent {unites}")
        print(f"    OK PM-1 {n}/20 plans declarent unite_exposition, "
              f"toutes 'annee' -- derive des fichiers")

    def test_PM_2_le_ZERO_EURO_se_prouve_par_la_borne_pas_par_la_phrase(self):
        """⚠️⚠️ CE QUI PROUVE « AUCUN EURO » N'EST PAS LE COMPTE DE PLANS.

        La phrase disait : *0/20 déclarent, DONC aucun euro*. Ce raisonnement
        est mort le jour où ils ont déclaré — alors qu'aucun euro n'avait
        bougé. La vraie preuve est que la borne DÉCLARÉE égale la borne par
        défaut. *Une conclusion juste tenue par une prémisse fausse est une
        dette, pas une garantie.*
        """
        for plan in _charges():
            self.assertEqual(
                borne_exposition(plan), PLAFOND_EXPOSITION,
                f"le plan {getattr(plan, 'nom', '?')} déclare une unité dont "
                f"la borne ({borne_exposition(plan)}) diffère du plafond "
                f"historique ({PLAFOND_EXPOSITION}) : DES EUROS BOUGENT sur "
                f"l'existant, et plus aucune phrase du dépôt ne le dit.")
        print(f"    OK PM-2 les 20 bornes declarees valent "
              f"{PLAFOND_EXPOSITION} = le plafond historique : zero euro PROUVE")

    def test_PM_3_le_delta_de_1B_se_derive_par_execution(self):
        """⚠️⚠️ LE CHIFFRE DE 1-B A PÉRIMÉ EN VINGT-QUATRE HEURES.

        La feuille de route affirmait 60 lignes (30 fréquence + 30 coût).
        `qualite/C8` a sorti le coût de la règle 1 le soir même : il est
        SIGNALÉ et GARDÉ. Le delta est de 30.

        On le dérive du comportement, jamais du texte.
        """
        plan = PlanTarifaire.depuis_yaml(str(_RACINE / 'plans' / 'auto.yaml'))
        e, f, c = plan.exposition, plan.cible_frequence, plan.cible_cout
        rng = np.random.default_rng(31)
        n = 1_000
        df = pd.DataFrame({
            e: np.ones(n), f: rng.integers(0, 3, n).astype(float),
            c: np.zeros(n),
            'prime_acquise': (200 + np.arange(n) * 0.01).round(2)})
        df[c] = np.where(df[f] > 0, rng.uniform(500, 5000, n).round(2), 0.0)
        df.loc[0:29, f] = -1.0
        df.loc[0:29, c] = 0.0
        df.loc[100:129, c] = -500.0
        df.loc[200:229, e] = 0.0

        rapport = controler_qualite(df.copy(), plan,
                                    qualite_validee_par='temoin')
        codes_exclus = {a.code for a in rapport.exclusions}
        codes_signales = {a.code for a in rapport.signalements}

        self.assertIn('frequence_negative', codes_exclus)
        self.assertNotIn(
            'cout_negatif', codes_exclus,
            "le coût est redevenu une EXCLUSION : le delta de 1-B repasse à "
            "60 lignes, et tout texte qui dit 30 devient faux.")
        self.assertIn(
            'cout_net_negatif', codes_signales,
            "le coût net négatif n'est plus SIGNALÉ : `qualite/C8` a régressé.")

        propre = rapport.dataframe_propre
        exclues = n - len(propre)
        self.assertEqual(
            exclues, 60,
            f"{exclues} lignes exclues au lieu de 60 (30 fréquence + "
            f"30 exposition)")
        self.assertEqual(
            int((propre[c] < 0).sum()), 30,
            "les coûts nets négatifs ne sont plus CONSERVÉS")
        print("    OK PM-3 couche : 60 exclues (freq 30 + expo 30), "
              "30 couts nets negatifs GARDES -> delta 1-B = 30 lignes")

    def test_PM_4_aucune_phrase_n_affirme_plus_le_compte_perime(self):
        """⚠️ LE SECOND SENS — la phrase morte ne doit pas repousser ailleurs.

        Assiette : les fichiers `.py` de production et les documents d'audit.
        On interdit la forme qui AFFIRME AU PRÉSENT ; la forme DATÉE est
        permise, et c'est toute la distinction. *Ce qui limite est sûr ; ce
        qui affirme est une dette.*
        """
        affirme = re.compile(
            r"(aucun des 20 plans ne déclare d'unité"
            r"|0\s*/?\s*20 plans\*{0,2} ne déclare d'unité"
            r"|60 lignes à fréquence ou coût)",
            re.IGNORECASE)
        cibles = ([_RACINE / 'core' / 'qualite_donnees.py']
                  + sorted((_RACINE / 'direction_non_vie' / 'tarification'
                            / 'audit_2026_08').glob('*.md')))
        fautifs = []
        for fichier in cibles:
            for i, ligne in enumerate(
                    fichier.read_text(encoding='utf-8').splitlines(), 1):
                # Une ligne qui CITE le defaut pour le dater est permise.
                if affirme.search(ligne) and 'AFFIRM' not in ligne.upper():
                    fautifs.append(f'{fichier.name}:{i}')
        self.assertEqual(
            fautifs, [],
            f"une phrase perimee affirme encore le present : {fautifs}")
        print(f"    OK PM-4 second sens : 0 affirmation perimee sur "
              f"{len(cibles)} fichiers, les formes DATEES restent permises")


if __name__ == '__main__':
    unittest.main(verbosity=2)
