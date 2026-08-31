"""Controles positifs — `conformite/C15` : un facteur DECLARE ne disparait plus
sans un mot.

CE QUE LE CONSTAT DIT, ET CE QUE LA TRACE A CORRIGE
────────────────────────────────────────────────────

La liste blanche de `construire_matrice_x` compare ce qu'elle RECOIT a ce qui
est PERMIS. **Elle ne peut donc rien dire de ce qui a ete retire AVANT elle.**
Violation plantee le 31/08 -- on retire UNE colonne declaree avant l'appel :

```
  temoin  (23 colonnes) -> 23 retenues | exclusions 0 | alertes 0
  amputee (22 colonnes) -> 22 retenues | exclusions 0 | alertes 0   <-- RIEN
```

C'est `plan/C3` -- << un `type` mal orthographie detruit un facteur en
silence >> -- ferme au niveau du plan et **rouvert un etage plus bas**.

⚠️⚠️ L'ASYMETRIE ENTRE CHEMINS LOCALISE LE DEFAUT. Six appelants de production,
et ils ne se ressemblent pas : `pipeline_tarifaire` et la demo passent
`plan.colonnes_produites()` -- **le contrat lui-meme, rien ne peut etre mange**.
`a3`, `a4`, `a5`, `a6` passent une liste **obtenue par soustraction**.

═══ ⛔⛔ CE QUE J'AVAIS AFFIRME, ET QUE LA MESURE A REFUTE ═══

J'avais annonce que trois signaux de conformite -- dont le filtre de genre
(CJUE C-236/09) -- s'ecrivaient neuf fois et n'etaient lus NULLE PART, et
recommande de rouvrir `conformite/C7`. **C'ETAIT FAUX, sur les trois points.**

Ma sonde cherchait des `ast.Attribute` ; le code fait
`getattr(self, 'exclusions_conformite', {})` -- un **`Call`** -- puis range la
valeur sous une **cle de dict**, lue par les trois services. *Le canal etait
complet et vivant ; ma sonde mesurait sa propre grammaire.*

> **L'absence d'une FORME SYNTAXIQUE n'est pas l'absence du FAIT.**

`conformite/C7` reste FERME, correctement. Le correctif est passe de quatre
pieces a trois : la tuyauterie existe, il n'y a qu'a y verser un fait de plus.

═══ ⚠️⚠️ ET LA MESURE A CORRIGE LA CONCEPTION UNE SECONDE FOIS ═══

Premiere version : une liste nue de colonnes, publiee en << ACTION REQUISE >>.
Execute sur un portefeuille NORMAL, elle criait deja -- `carburant_electrique`,
modalite one-hot d'un portefeuille sans vehicule electrique, donc **CONSTANTE**.
C'est legitime. *Un avertissement permanent est un avertissement qu'on cesse de
lire.*

Le motif voyage donc avec le fait, et **la gravite suit le motif** : seule une
colonne DECLAREE, presente et exploitable, RETIREE par un filtre en amont
appelle une action. ⚠️ La cause est derivee **dans la porte** -- elle recoit
deja `df` pour le garde-fou n°4 -- donc **en un seul endroit**, pas dans les
trois agents qui soustraient.

═══ AUCUN EURO, ET C'EST MESURE ═══

Version d'AVANT tiree du commit, chargee sous un nom de module distinct,
executee cote a cote sur 3 portefeuilles : **features retenues, exclusions,
alertes et execution du garde-fou n°4 IDENTIQUES -- 0 ecart.**
"""

from __future__ import annotations

import ast
import logging
import pathlib
import unittest
import warnings
from unittest import mock

import numpy as np
import pandas as pd

from core.conformite_reglementaire import (
    MOTIF_ECARTEE_FILTRE,
    construire_matrice_x,
    synthese_colonnes_plan_ecartees,
)
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
)
from direction_non_vie.tarification.a3_glm import agent as _a3mod
from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
from direction_non_vie.tarification.test_pipeline_agents import (
    _PLAN_AUTO,
    _portefeuille_auto,
)

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_SERVICES = _RACINE / 'direction_non_vie' / 'tarification' / 'services'


def _sans_bruit(fn, *a, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        precedent = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            return fn(*a, **kw)
        finally:
            logging.disable(precedent)


def _df_du_plan(n=200, seed=0):
    """Un dataframe portant TOUTES les colonnes declarees, toutes variables."""
    rng = np.random.default_rng(seed)
    cols = list(_PLAN_AUTO.colonnes_produites())
    df = pd.DataFrame({c: rng.normal(size=n) for c in cols})
    df['nb_sinistres'] = rng.poisson(0.2, n).astype(float)
    return df, cols


def _a3(r2, plan=_PLAN_AUTO):
    return _sans_bruit(
        AgentA3GLM(audit_path='/tmp', verbose=False).run, r2, plan=plan)


def _jusqu_a_a2(n=800, seed=3):
    df = _portefeuille_auto(n, seed=seed)
    r1 = _sans_bruit(AgentA1Ingestion(audit_path='/tmp', verbose=False).run,
                     dataframe=df, branche='non_vie', sous_branche='auto')
    return _sans_bruit(
        AgentA2Preprocessing(audit_path='/tmp', verbose=False).run,
        r1, plan=_PLAN_AUTO)


class TestLaPorteCONSTATE(unittest.TestCase):
    """PIECE A — elle voit l'absence, et elle ne revendique rien."""

    def test_LE_TEST_QUI_FERME_une_colonne_DECLAREE_jamais_recue_est_VUE(self):
        """⚠️⚠️ C'est la violation plantee du constat, devenue controle."""
        df, cols = _df_du_plan()
        kw = {'plan': _PLAN_AUTO, 'df': df, 'col_cible': 'nb_sinistres'}
        temoin = _sans_bruit(construire_matrice_x, list(cols),
                             contexte='temoin', **kw)
        self.assertEqual(temoin.ecartees_amont, {},
                         'le temoin signale une absence : le controle mesure '
                         'autre chose que ce qu il annonce')
        ampute = _sans_bruit(construire_matrice_x, [c for c in cols
                                                    if c != cols[0]],
                             contexte='ampute', **kw)
        self.assertEqual(sorted(ampute.ecartees_amont), [cols[0]])
        print(f"    CPE-1 colonne declaree retiree en amont -> VUE : "
              f"{sorted(ampute.ecartees_amont)}")

    def test_elle_ne_la_range_PAS_dans_les_exclusions(self):
        """⚠️⚠️ *Un instrument ne revendique pas un acte qu'il n'a pas commis.*
        Elle n'a pas ECARTE ce qu'elle n'a jamais recu."""
        df, cols = _df_du_plan()
        mx = _sans_bruit(construire_matrice_x, [c for c in cols
                                                if c != cols[0]],
                         plan=_PLAN_AUTO, df=df, col_cible='nb_sinistres',
                         contexte='ampute')
        self.assertNotIn(cols[0], mx.exclusions)
        self.assertEqual(mx.exclusions, {},
                         'la porte declare avoir exclu une colonne qu elle n a '
                         'jamais recue')
        print("    CPE-2 l'absence n'est PAS une exclusion : `exclusions` "
              "reste vide")

    def test_sans_plan_elle_ne_devine_RIEN(self):
        """⚠️ Sans contrat, il n'y a rien a comparer — et le dire vaut mieux
        que de rendre une liste trompeuse."""
        _, cols = _df_du_plan()
        mx = _sans_bruit(construire_matrice_x, cols[:3], contexte='sans plan')
        self.assertEqual(mx.ecartees_amont, {})
        print("    CPE-3 sans plan : aucune absence inventee")


class TestLeMotifVoyageAvecLeFait(unittest.TestCase):
    """⚠️⚠️ SANS LUI, LE SIGNAL SERAIT DU BRUIT PERMANENT."""

    def test_les_causes_sont_DERIVEES_pas_supposees(self):
        df, cols = _df_du_plan()
        df['constante'] = 1.0
        df['texte'] = 'x'
        plan = _PLAN_AUTO
        with mock.patch.object(
                type(plan), 'colonnes_produites',
                lambda self: list(cols) + ['constante', 'texte', 'jamais_la']):
            mx = _sans_bruit(construire_matrice_x, list(cols), plan=plan,
                             df=df, col_cible='nb_sinistres',
                             contexte='causes')
        m = mx.ecartees_amont
        self.assertIn('constante', m['constante'])
        self.assertIn('non numerique', m['texte'])
        self.assertIn('absente du dataframe', m['jamais_la'])
        print(f"    CPE-4 trois causes derivees : "
              f"{ {k: v[:28] for k, v in sorted(m.items())} }")

    def test_la_GRAVITE_suit_le_MOTIF_jamais_le_compte(self):
        """⚠️⚠️ Mesure du 31/08 : sur un portefeuille NORMAL,
        `carburant_electrique` est ecartee car CONSTANTE. Crier a chaque
        execution rendrait l'avertissement invisible."""
        anodin = synthese_colonnes_plan_ecartees(
            {'carburant_electrique': 'constante (variance nulle) sur ce '
                                     'portefeuille'}, 'auto')
        self.assertNotIn('ACTION REQUISE', anodin)
        grave = synthese_colonnes_plan_ecartees(
            {'age': MOTIF_ECARTEE_FILTRE}, 'auto')
        self.assertIn('ACTION REQUISE', grave)
        self.assertIn('age', grave)
        print("    CPE-5 constante -> aucune action ; retiree par un filtre "
              "-> ACTION REQUISE")

    def test_second_sens_rien_a_dire_RIEN_de_publie(self):
        """⚠️ Un libelle qui parle toujours ne signale plus rien."""
        self.assertIsNone(synthese_colonnes_plan_ecartees(None))
        self.assertIsNone(synthese_colonnes_plan_ecartees({}))
        print("    CPE-6 aucune ecartee -> None, rien n'est publie")


class TestLeTrajetJusquAuLIVRABLE(unittest.TestCase):
    """PIECE B — la lecon du jour : une surface signee se verifie PAR EXECUTION."""

    def test_LE_TRAJET_COMPLET_A3_porte_la_cle(self):
        r2 = _jusqu_a_a2()
        r3 = _a3(r2)
        self.assertIn('colonnes_plan_ecartees', r3)
        self.assertIsInstance(r3['colonnes_plan_ecartees'], dict)
        print(f"    CPE-7 A3 publie la cle : "
              f"{sorted(r3['colonnes_plan_ecartees'])}")

    def test_un_facteur_DECLARE_mange_par_la_liste_noire_ATTEINT_le_livrable(self):
        """⚠️⚠️ LE CONTROLE QUI FERME LE CONSTAT. On plante le defaut REEL —
        la liste noire d'A3 avale un facteur declare — et on verifie qu'il
        ressort jusqu'au texte que lira l'actuaire."""
        r2 = _jusqu_a_a2()
        avant = _a3(r2)['colonnes_plan_ecartees']
        self.assertNotIn('age', avant, "'age' est deja ecartee sans plant : "
                                       "le controle ne prouverait rien")
        with mock.patch.object(_a3mod, 'COLS_A_EXCLURE',
                               sorted(set(_a3mod.COLS_A_EXCLURE) | {'age'})):
            apres = _a3(r2)['colonnes_plan_ecartees']
        self.assertIn('age', apres)
        self.assertEqual(apres['age'], MOTIF_ECARTEE_FILTRE)
        texte = synthese_colonnes_plan_ecartees(apres, 'auto')
        self.assertIn('ACTION REQUISE', texte)
        self.assertIn('age', texte)
        print(f"    CPE-8 facteur declare avale -> publie : "
              f"{texte[:72]}...")

    def test_les_TROIS_services_publient_le_libelle(self):
        """⚠️ Mesure PAR AST. *Une source unique que personne n'appelle est de
        la plomberie morte* — le motif de `socle/C2`."""
        appelants = []
        for f in sorted(_SERVICES.glob('*.py')):
            arbre = ast.parse(f.read_text(encoding='utf-8'))
            if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id == 'synthese_colonnes_plan_ecartees'
                   for n in ast.walk(arbre)):
                appelants.append(f.name)
        self.assertEqual(
            appelants,
            ['rapport_equipe_tarif.py', 'rapport_modeles_tarif.py',
             'tarif_excel.py'],
            f'le libelle n est publie que par {appelants}')
        print(f"    CPE-9 les 3 services publient le libelle : {appelants}")


class TestAucunEuroDeplace(unittest.TestCase):

    def test_les_features_retenues_sont_INCHANGEES(self):
        """⚠️⚠️ Mesure AVANT/APRES du 31/08 : version d'avant tiree du commit,
        chargee sous un nom distinct, 3 portefeuilles -- **0 ecart** sur les
        features, les exclusions, les alertes et l'execution du garde-fou n°4.
        Ce controle fige l'invariant : ce que la porte RETIENT ne depend pas de
        ce qu'elle CONSTATE."""
        df, cols = _df_du_plan()
        kw = {'plan': _PLAN_AUTO, 'df': df, 'col_cible': 'nb_sinistres'}
        complet = _sans_bruit(construire_matrice_x, list(cols),
                              contexte='complet', **kw)
        ampute = _sans_bruit(construire_matrice_x, [c for c in cols
                                                    if c != cols[0]],
                             contexte='ampute', **kw)
        self.assertEqual(list(complet), list(cols))
        self.assertEqual(list(ampute), [c for c in cols if c != cols[0]])
        self.assertEqual(len(complet.exclusions), 0)
        self.assertEqual(len(ampute.exclusions), 0)
        print(f"    CPE-10 features inchangees : {len(list(complet))} "
              f"retenues, 0 exclusion, l'absence ne retire rien")


if __name__ == '__main__':
    unittest.main()
