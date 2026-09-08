"""LE CHAMP QUI SIGNAIT SANS AGIR -- point (5) du chantier.

`plan.cout_par_sinistre` est valide, lu depuis le YAML, et il entre dans la
CHARGE HACHEE de l'empreinte SHA-256 du plan. Le bump de schema `s4 -> s5` du
01/09/2026 le justifie ainsi : << elle change l'ASSIETTE du seuil
d'ecretement >>.

  ***Releve AST du 08/09/2026*** : les CINQ sites de production qui appellent
  `construire_cible_severite` ne passaient JAMAIS `couts_par_sinistre`, et
  **0 plan sur 20** declarait le champ. Mesure sur `test_plan_invariants.AUTO`,
  le plan de reference du depot : deux plans n'en differant QUE par lui rendent
  `s9:7ce0606a6b19e717` et `s9:a777997ee5fa2be3` -- deux signatures opposables
  pour un tarif identique au bit pres. *(Digests relus le 08/09/2026 : le bump
  `s8` -> `s9` de `regime_fiscal` les a deplaces.)*

*Un champ qui n'agit pas ne doit pas signer.* Il agit desormais.

⚠️⚠️ CE QUE L'ASSIETTE CHANGE, MESURE (4 000 contrats, 08/09/2026) :

    sin./contrat   seuil << total >>   seuil << par sinistre >>   prime grave
             1,1              40 807                     31 128   112 -> 140
             4,0              70 233                     35 615   322 -> 557
             8,0             105 015                     33 875   276 -> 1 017

Le seuil << par sinistre >> reste STABLE ; l'autre suit le nombre de sinistres
du contrat. *Il n'ecrete pas les graves, il ecrete les nombreux.* Et l'effet ne
se lit PAS sur la severite ecretee (-1,5 a -3,7 %) : il se lit sur la charge
grave a reintegrer, de +25 % a +269 %.

⚠️ UN SECOND DEFAUT, TROUVE EN BRANCHANT. `SeuilGrave.assiette` vaut
`'par_sinistre'` PAR DEFAUT, et sa docstring dit que cela EXIGE
`cout_par_sinistre`. Rien ne le verifiait : un plan declarant un `seuil_grave`
sans nommer son assiette y tombait, et l'ecretement portait sur le TOTAL du
contrat pendant que le document signe annoncait le contraire.

  CS-1  sans declaration : `None`, et le tarif ne bouge pas ;
  CS-2  colonne DECLAREE et ABSENTE : leve, ne se tait pas ;
  CS-3  declaree et presente : l'assiette change REELLEMENT ;
  CS-4  le garde croise : `par_sinistre` sans colonne est REFUSE ;
  CS-5  son second sens : `total_contrat` sans colonne est ACCEPTE ;
  CS-6  les CINQ sites de production passent le parametre ;
  CS-7  l'empreinte atteste enfin quelque chose : deux plans qui n'en
        different que par ce champ ne tarifent PAS pareil.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""

from __future__ import annotations

import ast
import dataclasses
import os
import pathlib
import sys
import unittest

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire, SeuilGrave
from core.severite import (
    construire_cible_severite,
    couts_par_sinistre_du_plan,
)

_SITES = (
    ('a3_glm/agent.py', 2),
    ('pipeline_agents.py', 1),
    ('pipeline_tarifaire.py', 2),
)


def _plan():
    return PlanTarifaire.depuis_yaml(
        os.path.join(_RACINE, 'plans', 'auto.yaml'))


def _portefeuille(n=3000, sin_par_contrat=4.0, graine=11):
    """Des sinistres INDIVIDUELS, et le total du contrat qui en decoule.

    ⚠️ Le total est la SOMME des montants : le socle refuse une jointure
    fausse, et il a raison -- une jointure fausse ecreterait au hasard."""
    rng = np.random.default_rng(graine)
    nb = rng.poisson(sin_par_contrat, n)
    montants = [rng.lognormal(7.0, 1.35, k) if k else np.array([])
                for k in nb]
    return pd.DataFrame({
        'cout_total_sinistres': [float(m.sum()) for m in montants],
        'nb_sinistres': nb.astype(float),
        'exposition': np.ones(n),
        'montants_sinistres': montants,
    })


class TestCoutParSinistreBranche(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.plan = _plan()
        cls.df = _portefeuille()

    # ── l'accesseur, dans ses trois etats ────────────────────────────────
    def test_CS1_SECOND_SENS_sans_declaration_rien_ne_change(self):
        """⚠️⚠️ LE CAS DES VINGT PLANS LIVRES. Brancher ne doit RIEN changer
        pour eux : c'est ce qui rend le correctif posable."""
        self.assertIsNone(couts_par_sinistre_du_plan(self.df, self.plan))
        self.assertIsNone(couts_par_sinistre_du_plan(self.df, None))
        # et la cible construite est identique a celle d'avant le branchement
        avec = construire_cible_severite(
            self.df['cout_total_sinistres'], self.df['nb_sinistres'],
            self.df['exposition'],
            couts_par_sinistre=couts_par_sinistre_du_plan(self.df, self.plan))
        sans = construire_cible_severite(
            self.df['cout_total_sinistres'], self.df['nb_sinistres'],
            self.df['exposition'])
        self.assertEqual(avec.seuil_ecretement, sans.seuil_ecretement)
        self.assertEqual(avec.prime_grave_unitaire, sans.prime_grave_unitaire)
        print('    CS-1 sans declaration : None, et la cible est identique')

    def test_CS2_une_colonne_DECLAREE_et_ABSENTE_leve(self):
        """⚠️⚠️ ELLE NE SE TAIT PAS. Une declaration que le fichier ne tient
        pas ferait ecreter sur le TOTAL pendant que le plan signe annonce
        << par sinistre >>. *Le silence serait le pire des trois etats.*"""
        p = dataclasses.replace(self.plan,
                                cout_par_sinistre='montants_sinistres')
        with self.assertRaises(ValueError) as leve:
            couts_par_sinistre_du_plan(pd.DataFrame({'autre': [1.0]}), p)
        self.assertIn('montants_sinistres', str(leve.exception))
        self.assertIn('ABSENTE', str(leve.exception))
        print('    CS-2 colonne declaree et absente : leve, et la NOMME')

    def test_CS3_declaree_et_presente_l_assiette_change_REELLEMENT(self):
        """⚠️⚠️ LE CONSTAT, MESURE. Et l'ecart ne se lit PAS sur la severite
        ecretee : il se lit sur la charge grave a reintegrer."""
        p = dataclasses.replace(self.plan,
                                cout_par_sinistre='montants_sinistres')
        cps = couts_par_sinistre_du_plan(self.df, p)
        self.assertIsNotNone(cps)
        self.assertEqual(len(cps), len(self.df))
        total = construire_cible_severite(
            self.df['cout_total_sinistres'], self.df['nb_sinistres'],
            self.df['exposition'])
        par_sin = construire_cible_severite(
            self.df['cout_total_sinistres'], self.df['nb_sinistres'],
            self.df['exposition'], couts_par_sinistre=cps)
        self.assertLess(
            par_sin.seuil_ecretement, total.seuil_ecretement,
            "le seuil « par sinistre » n'est pas plus bas que le seuil "
            "« total » : l'assiette n'a pas change")
        self.assertGreater(
            par_sin.n_graves, total.n_graves,
            "l'assiette « par sinistre » ne trouve pas plus de graves : "
            "elle ecrete encore les nombreux")
        ecart = (par_sin.prime_grave_unitaire
                 / max(total.prime_grave_unitaire, 1e-9) - 1)
        self.assertGreater(
            abs(ecart), 0.10,
            f'la charge grave a reintegrer ne bouge que de {100*ecart:.1f} % : '
            f'le branchement ne changerait rien de mesurable')
        print(f'    CS-3 seuil {total.seuil_ecretement:,.0f} -> '
              f'{par_sin.seuil_ecretement:,.0f} · graves '
              f'{total.n_graves} -> {par_sin.n_graves} · charge grave '
              f'{100*ecart:+.0f} %')

    # ── le garde croise du plan ──────────────────────────────────────────
    def test_CS4_une_assiette_qu_on_ne_peut_pas_tenir_est_REFUSEE(self):
        """⚠️⚠️ `par_sinistre` est la valeur PAR DEFAUT de `SeuilGrave` : un
        plan qui declare un seuil sans nommer son assiette y tombait, et
        l'ecretement portait sur le TOTAL pendant que le document signe
        annoncait le contraire."""
        for assiette in ('par_sinistre', None):
            with self.subTest(assiette=assiette or 'defaut'):
                sg = (SeuilGrave(50000.0, 'par_sinistre', 'traite')
                      if assiette else SeuilGrave(50000.0, source='traite'))
                with self.assertRaises(ValueError) as leve:
                    dataclasses.replace(self.plan, seuil_grave=sg)
                self.assertIn('cout_par_sinistre', str(leve.exception))
        print('    CS-4 `par_sinistre` sans colonne : refuse, defaut compris')

    def test_CS5_SECOND_SENS_total_contrat_sans_colonne_est_ACCEPTE(self):
        """⚠️ Sans ce sens, un garde qui refuserait TOUT `seuil_grave`
        passerait CS-4 -- et on aurait interdit une declaration legitime."""
        p = dataclasses.replace(
            self.plan,
            seuil_grave=SeuilGrave(50000.0, 'total_contrat', 'traite'))
        self.assertIsNotNone(p.seuil_grave)
        self.assertEqual(p.seuil_grave.assiette, 'total_contrat')
        # et `par_sinistre` AVEC la colonne passe aussi
        p2 = dataclasses.replace(
            self.plan, cout_par_sinistre='montants_sinistres',
            seuil_grave=SeuilGrave(50000.0, 'par_sinistre', 'traite'))
        self.assertEqual(p2.seuil_grave.assiette, 'par_sinistre')
        print('    CS-5 `total_contrat` seul, et `par_sinistre` + colonne : ok')

    # ── le branchement lui-meme ──────────────────────────────────────────
    def test_CS6_les_CINQ_sites_de_production_passent_le_parametre(self):
        """⚠️ RELEVE PAR AST, PAS AU TEXTE : on compte les APPELS de
        `construire_cible_severite` et on exige que chacun porte le mot-cle.
        Un site qui l'oublierait ferait taire le champ sans que rien ne
        bouge -- c'est exactement l'etat d'avant."""
        total, sans = 0, []
        for rel, attendu in _SITES:
            chemin = pathlib.Path(_ICI) / rel
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            appels = [n for n in ast.walk(arbre)
                      if isinstance(n, ast.Call)
                      and getattr(n.func, 'id',
                                  getattr(n.func, 'attr', None))
                      == 'construire_cible_severite']
            self.assertEqual(
                len(appels), attendu,
                f'{rel} : {len(appels)} appel(s) au lieu de {attendu} — '
                f'le releve de ce test est perime')
            for a in appels:
                total += 1
                if 'couts_par_sinistre' not in {k.arg for k in a.keywords}:
                    sans.append(f'{rel}:{a.lineno}')
        self.assertEqual(
            sans, [],
            f'site(s) de production qui ignorent encore le champ : {sans}')
        self.assertEqual(total, 5, f'{total} sites au lieu de 5')
        print(f'    CS-6 les {total} sites de production passent le parametre')

    def test_CS7_l_empreinte_atteste_enfin_quelque_chose(self):
        """⚠️⚠️ LE POINT QUI FERME LE CONSTAT. Le champ entre dans la charge
        hachee de l'empreinte OPPOSABLE, et le bump `s4 -> s5` le justifie par
        << elle change l'ASSIETTE du seuil >>. Il ne la changeait pas.

        On exige les DEUX moities : deux empreintes DIFFERENTES, et deux
        tarifs DIFFERENTS. *Une signature qui distingue deux plans identiques
        au bit pres n'atteste rien ; c'est le lien entre les deux qui la rend
        opposable.*"""
        sans = dataclasses.replace(self.plan, cout_par_sinistre=None)
        avec = dataclasses.replace(self.plan,
                                   cout_par_sinistre='montants_sinistres')
        self.assertNotEqual(sans.empreinte(), avec.empreinte(),
                            'le champ ne signe plus')
        c_sans = construire_cible_severite(
            self.df['cout_total_sinistres'], self.df['nb_sinistres'],
            self.df['exposition'],
            couts_par_sinistre=couts_par_sinistre_du_plan(self.df, sans))
        c_avec = construire_cible_severite(
            self.df['cout_total_sinistres'], self.df['nb_sinistres'],
            self.df['exposition'],
            couts_par_sinistre=couts_par_sinistre_du_plan(self.df, avec))
        self.assertNotEqual(
            c_sans.prime_grave_unitaire, c_avec.prime_grave_unitaire,
            'deux empreintes differentes pour une charge grave IDENTIQUE : '
            "l'empreinte atteste encore une difference que le tarif ne porte "
            'pas')
        print(f'    CS-7 empreintes distinctes ET charge grave '
              f'{c_sans.prime_grave_unitaire:,.0f} -> '
              f'{c_avec.prime_grave_unitaire:,.0f}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
