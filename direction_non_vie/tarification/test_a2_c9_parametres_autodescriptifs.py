"""Controles positifs -- `a2/C9` : une moyenne rangee sous << medianes >>.

═══ ⛔⛔ LE CONSTAT, ET CE QUI MANQUAIT VRAIMENT ═══

`cle = 'modes' if strategie == 'mode' else 'medianes'` : toute strategie
non-mode -- donc la MOYENNE -- atterrissait sous une etiquette qui dit mediane.
Mesure du 01/09/2026, imputation declenchee sur un portefeuille reel :

    medianes = {'age': 50.6468}        mediane REELLE de age = 50.0

**Une moyenne rangee sous une etiquette qui dit mediane**, dans le dict invoque
au titre de la reproductibilite S2.

⚠️⚠️ CE N'ETAIT PAS UN NOM QUI MANQUAIT, C'ETAIT UNE INFORMATION. Un fichier de
schema 1 porte `{'age': 50.6468}` **sans dire** si c'est une mediane ou une
moyenne, et la strategie n'est PAS re-derivable depuis le JSON :
`_categorie_imputation` a besoin de la SERIE DE DONNEES, pas du nom de colonne.

> *Repartir un ancien bloc entre `medianes` et `moyennes` serait une DEVINETTE
> sur un parametre de reproductibilite.*

═══ LES TROIS PIECES, ARBITREES ENSEMBLE LE 01/09/2026 ═══

| | ce que ça ferme |
|---|---|
| la cle DERIVE de la strategie | l'etiquette cesse de mentir |
| chaque valeur porte SA strategie | un futur fichier n'a plus rien a deviner |
| `PARAMS_SCHEMA` + un lecteur qui migre | un ancien fichier reste lisible |

⚠️ LE LECTEUR N'EXISTAIT PAS. `charger_parametres` avait ete supprimee
(mecanisme mort), donc le fichier etait **ecrit et relu par personne** :
*un format persiste sans lecteur n'est pas un format, c'est un depot.*

⚠️ `modes` MIGRE SANS PERTE, et ce n'est pas une supposition : en schema 1, la
ligne n'y mettait QUE la strategie `mode`. L'information est certaine. Le bloc
`medianes`, lui, est CONSERVE tel quel sous `imputations_heritees` -- marque,
jamais efface, jamais devine.
"""

from __future__ import annotations

import ast
import json
import pathlib
import tempfile
import unittest

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire
from demos.pipeline_3lob_a1_a6_demo import portefeuille_auto
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing import agent as _a2mod
from direction_non_vie.tarification.a2_preprocessing.agent import (
    _CALCUL_IMPUTATION,
    _CLE_PARAMETRE,
    CLE_HERITEE,
    PARAMS_SCHEMA,
    AgentA2Preprocessing,
    lire_parametres_a2,
)

_SOURCE = pathlib.Path(_a2mod.__file__).read_text(encoding='utf-8')
_RACINE = pathlib.Path(_a2mod.__file__).parents[3]

#: Un fichier de schema 1 AVEC du contenu — la vraie forme a migrer.
_SCHEMA_1 = {
    'medianes': {'age': 50.6468, 'capital': 12000.0},
    'modes': {'csp': 'employe'},
    'winsor_bounds': {}, 'encodeurs': {}, 'stats_expo': {},
    'version': '1.0', 'timestamp': '2026-08-01T00:00:00',
    'sous_branche': 'auto',
}


def _ecrire(dossier, contenu, nom='params_a2_auto.json'):
    chemin = pathlib.Path(dossier) / nom
    chemin.write_text(json.dumps(contenu), encoding='utf-8')
    return chemin


class TestA2C9ParametresAutodescriptifs(unittest.TestCase):
    """`a2/C9` : l'etiquette, l'information, et la transition."""

    # ── Pièce 1 : la clé DÉRIVE de la stratégie ────────────────────────────

    def test_AC_1_la_cle_derive_de_la_strategie(self):
        """`a2/C9` : plus aucun `if` ne repartit les valeurs."""
        self.assertEqual(
            set(_CLE_PARAMETRE), set(_CALCUL_IMPUTATION),
            "`_CLE_PARAMETRE` et `_CALCUL_IMPUTATION` ne couvrent pas les "
            "memes strategies : une strategie sans nom de seau retomberait "
            "dans un repli, et c'est exactement `a2/C9`")
        self.assertEqual(len(set(_CLE_PARAMETRE.values())),
                         len(_CLE_PARAMETRE),
                         'deux strategies partagent un seau : le nom cesse de '
                         'dire ce que le seau contient')
        # Le `if` fautif ne doit pas revenir, sous aucune forme.
        for n in ast.walk(ast.parse(_SOURCE)):
            if isinstance(n, ast.IfExp):
                litteraux = {c.value for c in ast.walk(n)
                             if isinstance(c, ast.Constant)}
                self.assertFalse(
                    {'modes', 'medianes'} <= litteraux,
                    f"l.{n.lineno} : un ternaire repartit de nouveau entre "
                    f"`modes` et `medianes` — c'est la ligne de `a2/C9`")

    # ── Pièce 2 : chaque valeur porte SA stratégie ─────────────────────────

    def test_AC_2_LE_TEST_QUI_FERME_une_moyenne_va_sous_moyennes(self):
        """`a2/C9` : par EXECUTION, sur le vrai chemin d'imputation."""
        plan = PlanTarifaire.depuis_yaml(str(_RACINE / 'plans' / 'auto.yaml'))
        d = pathlib.Path(tempfile.mkdtemp())
        df = portefeuille_auto(3000, np.random.default_rng(3))
        df.loc[df.index[:200], 'age'] = np.nan
        r1 = AgentA1Ingestion(base_path=str(d / 'b'), audit_path=str(d / 'a'),
                              verbose=False).run(
            branche='non_vie', sous_branche='auto', dataframe=df, plan=plan)
        a2 = AgentA2Preprocessing(models_path=str(d / 'm'),
                                  audit_path=str(d / 'a'), verbose=False)
        a2.run(result_a1=r1, plan=plan)
        p = a2.parametres
        self.assertEqual(
            p['medianes'], {},
            f"une valeur est rangee sous `medianes` alors que la strategie "
            f"d'`age` est la MOYENNE : {p['medianes']}")
        self.assertIn('age', p['moyennes'])
        entree = p['moyennes']['age']
        self.assertEqual(entree['strategie'], 'mean')
        # ⚠️ Le FAIT, pas seulement le rangement : c'est bien la moyenne.
        moyenne = float(pd.Series(df['age']).mean())
        mediane = float(pd.Series(df['age']).median())
        self.assertAlmostEqual(entree['valeur'], moyenne, places=6)
        self.assertNotAlmostEqual(
            entree['valeur'], mediane, places=3,
            msg='la valeur egale la mediane : le cas ne prouve rien')

    def test_AC_3_le_seau_et_la_strategie_ne_peuvent_pas_se_contredire(self):
        """⚠️ La redondance EST le controle : deux sources, un desaccord visible."""
        plan = PlanTarifaire.depuis_yaml(str(_RACINE / 'plans' / 'auto.yaml'))
        d = pathlib.Path(tempfile.mkdtemp())
        df = portefeuille_auto(2000, np.random.default_rng(5))
        df.loc[df.index[:150], 'age'] = np.nan
        df.loc[df.index[:150], 'csp'] = None
        r1 = AgentA1Ingestion(base_path=str(d / 'b'), audit_path=str(d / 'a'),
                              verbose=False).run(
            branche='non_vie', sous_branche='auto', dataframe=df, plan=plan)
        a2 = AgentA2Preprocessing(models_path=str(d / 'm'),
                                  audit_path=str(d / 'a'), verbose=False)
        a2.run(result_a1=r1, plan=plan)
        attendu = {v: k for k, v in _CLE_PARAMETRE.items()}
        vus = 0
        for seau, strategie in attendu.items():
            for col, entree in (a2.parametres.get(seau) or {}).items():
                vus += 1
                self.assertEqual(
                    entree['strategie'], strategie,
                    f"'{col}' est dans le seau '{seau}' mais porte la "
                    f"strategie '{entree['strategie']}' : le nom et "
                    f"l'information se contredisent")
        self.assertGreater(vus, 0, 'aucune imputation : le cas ne prouve rien')

    # ── Pièce 3 : le schéma, et le lecteur qui migre ───────────────────────

    def test_AC_4_le_fichier_persiste_porte_son_SCHEMA(self):
        """`a2/C9` : `version` n'a jamais bouge — c'est `schema` qui migre."""
        plan = PlanTarifaire.depuis_yaml(str(_RACINE / 'plans' / 'auto.yaml'))
        d = pathlib.Path(tempfile.mkdtemp())
        df = portefeuille_auto(1500, np.random.default_rng(7))
        r1 = AgentA1Ingestion(base_path=str(d / 'b'), audit_path=str(d / 'a'),
                              verbose=False).run(
            branche='non_vie', sous_branche='auto', dataframe=df, plan=plan)
        AgentA2Preprocessing(models_path=str(d / 'm'), audit_path=str(d / 'a'),
                             verbose=False).run(result_a1=r1, plan=plan)
        ecrit = json.loads((d / 'm' / 'params_a2_auto.json').read_text(
            encoding='utf-8'))
        self.assertEqual(ecrit.get('schema'), PARAMS_SCHEMA)
        self.assertGreaterEqual(PARAMS_SCHEMA, 2)

    def test_AC_5_LE_TEST_QUI_FERME_un_ancien_fichier_reste_lisible(self):
        """`a2/C9` : le coeur de la transition — et RIEN n'est devine."""
        d = tempfile.mkdtemp()
        migre = lire_parametres_a2(_ecrire(d, dict(_SCHEMA_1)))
        self.assertEqual(migre['schema'], PARAMS_SCHEMA)
        # `modes` : migration SANS PERTE, parce que l'information est CERTAINE.
        self.assertEqual(migre['modes'],
                         {'csp': {'valeur': 'employe', 'strategie': 'mode'}})
        # Le bloc ambigu : CONSERVE, jamais reparti.
        herite = migre[CLE_HERITEE]
        self.assertEqual(herite['valeurs'], _SCHEMA_1['medianes'])
        self.assertIsNone(
            herite['strategie'],
            "une strategie a ete attribuee a un bloc de schema 1 : elle n'y "
            "a jamais ete persistee, donc c'est une DEVINETTE")
        self.assertIn('indiscernables', herite['note'])
        # ⚠️ Et les seaux du schema 2 restent VIDES : rien n'y a ete verse.
        self.assertEqual(migre['medianes'], {})
        self.assertEqual(migre['moyennes'], {})

    def test_AC_6_un_schema_PLUS_RECENT_leve(self):
        """⚠️ Le lire comme un ancien produirait des parametres faux."""
        d = tempfile.mkdtemp()
        with self.assertRaises(ValueError) as ctx:
            lire_parametres_a2(_ecrire(d, dict(_SCHEMA_1,
                                               schema=PARAMS_SCHEMA + 7)))
        self.assertIn('plus', str(ctx.exception).lower())
        with self.assertRaises(ValueError):
            lire_parametres_a2(_ecrire(d, dict(_SCHEMA_1, schema='deux'),
                                       nom='b.json'))
        with self.assertRaises(TypeError):
            lire_parametres_a2(_ecrire(d, [1, 2, 3], nom='c.json'))

    def test_AC_7_un_fichier_de_schema_2_passe_INTACT(self):
        """⚠️ Second sens : migrer ce qui n'a pas besoin de l'etre serait pire."""
        d = tempfile.mkdtemp()
        recent = {
            'medianes': {}, 'moyennes': {'age': {'valeur': 50.6,
                                                 'strategie': 'mean'}},
            'modes': {}, 'winsor_bounds': {}, 'encodeurs': {},
            'stats_expo': {}, 'version': '1.0', 'schema': PARAMS_SCHEMA,
            'timestamp': None, 'sous_branche': 'auto',
        }
        lu = lire_parametres_a2(_ecrire(d, recent))
        self.assertEqual(lu, recent)
        self.assertNotIn(
            CLE_HERITEE, lu,
            "un fichier deja au schema courant a ete 'migre' : le bloc "
            "herite n'a rien a y faire")


if __name__ == '__main__':
    unittest.main(verbosity=2)
