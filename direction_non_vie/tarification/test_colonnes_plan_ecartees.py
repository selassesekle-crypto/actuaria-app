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
from typing import ClassVar
from unittest import mock

import numpy as np
import pandas as pd

from core.conformite_reglementaire import (
    MOTIF_ECARTEE_FILTRE,
    MOTIF_MOTIF_ABSENT,
    construire_matrice_x,
    fusionner_ecartees_amont,
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


class TestLeMotifSURVIT_a_A6(unittest.TestCase):
    """PIECE D -- `conformite/C16` : LE TRAJET QUE PERSONNE NE TRAVERSAIT.

    ⚠️⚠️ CE FICHIER PORTAIT DEJA DIX CONTROLES, ET AUCUN N'A VU LE DEFAUT.
    `CPE-7` verifie qu'A3 porte la cle ; `CPE-9` verifie **PAR AST** que les
    trois services appellent la synthese. Entre les deux il y a A6 -- et
    *un appel ECRIT dans le source n'est pas un appel qui REUSSIT.*

    A6 agregeait les tables `{colonne: motif}` d'A3, A4 et A5 dans un `set` :
    il n'en restait que les cles. La synthese faisait `dict(liste)` et LEVAIT.

    ```
      Excel A6, colonnes_plan_ecartees vide         : 10 977 octets
      Excel A6, UNE colonne ecartee (cas ORDINAIRE) :      0 octet
    ```

    ⚠️⚠️ ET CE N'ETAIT PAS UN CRASH : les trois surfaces appellent dans un
    `try` qui rend `b''` sur un `logger.warning`. *Un echec bruyant se voit ;
    un rapport signe qui disparait en silence, non.*

    ⚠️ Le second effet est pire que le premier : la gravite se decide **sur le
    motif**, donc l'alerte << ACTION REQUISE -- facteur DECLARE, exploitable,
    RETIRE par un filtre amont >> ne pouvait plus JAMAIS se declencher sur le
    chemin agent.
    """

    _A3: ClassVar[dict] = {'carburant_electrique': 'constante (variance nulle)'}

    def test_CPE_11_A6_rend_une_TABLE_comme_ses_sources_pas_des_noms(self):
        """⚠️⚠️ L'ASYMETRIE, LA OU ELLE ETAIT. Une sentinelle exige deja d'A3
        un `dict` (`CPE-7`) ; A6 etait le SEUL a rompre le contrat.

        Assiette : les valeurs des deux cles de sortie d'A6, par AST.
        """
        src = (_RACINE / 'direction_non_vie' / 'tarification' / 'a6_comparaison'
               / 'agent.py').read_text(encoding='utf-8')
        vus = [ast.unparse(v)
               for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Dict)
               for c, v in zip(n.keys, n.values)
               if isinstance(c, ast.Constant)
               and c.value in ('colonnes_plan_ecartees',
                               'colonnes_exemptees_effet')]
        self.assertTrue(vus, "les cles de sortie d'A6 ont disparu")
        aplatis = [v for v in vus if v.startswith('sorted(')]
        self.assertEqual(
            aplatis, [],
            f"A6 aplatit encore une table en noms : {aplatis} -- le motif "
            f"n'atteindra pas le rapport signe")
        print(f"    CPE-11 les {len(vus)} sorties d'A6 portent une TABLE, "
              f"0 aplatissement")

    def test_CPE_12_la_fusion_prend_LE_PIRE_et_l_ordre_ne_decide_pas(self):
        """⚠️⚠️ `update()` GARDAIT LE DERNIER AGENT DE LA BOUCLE, EN SILENCE.

        Deux agents peuvent donner deux motifs : leurs dataframes different.
        *C'est la lecon deja ecrite dans A6 pour `agreger_controle_effet` --
        deux agents sur la meme cle s'ecrasaient, un motif sur deux
        disparaissait.* Un seul motif appelle une action : il l'emporte.
        """
        anodin = {'x': 'constante (variance nulle)'}
        grave = {'x': MOTIF_ECARTEE_FILTRE}
        self.assertEqual(fusionner_ecartees_amont(anodin, grave)['x'],
                         MOTIF_ECARTEE_FILTRE)
        self.assertEqual(
            fusionner_ecartees_amont(grave, anodin)['x'], MOTIF_ECARTEE_FILTRE,
            "l'ordre des agents decide du motif publie : le resultat depend "
            "de la boucle, pas des faits")
        # ⚠️ SECOND SENS : le pire ne doit pas ETEINDRE les autres colonnes.
        melange = fusionner_ecartees_amont(anodin, grave, {'y': 'absente'})
        self.assertEqual(sorted(melange), ['x', 'y'])
        print("    CPE-12 le PIRE l'emporte dans les DEUX ordres, "
              "les autres colonnes survivent")

    def test_CPE_13_des_noms_nus_ne_font_PAS_inventer_une_cause(self):
        """⚠️⚠️ *Une cause inventee est pire qu'une cause manquante.*

        La normalisation rend l'echec impossible ; elle ne doit pas rendre le
        texte faux. Des noms sans table recoivent un motif qui DIT que la
        cause n'a pas ete transmise -- jamais un motif plausible.
        """
        t = fusionner_ecartees_amont(['zone'])
        self.assertEqual(t, {'zone': MOTIF_MOTIF_ABSENT})
        self.assertNotEqual(
            t['zone'], MOTIF_ECARTEE_FILTRE,
            "des noms nus declenchent << ACTION REQUISE >> : le systeme "
            "invente la gravite qu'il ne connait pas")
        texte = synthese_colonnes_plan_ecartees(t, 'auto')
        self.assertNotIn('ACTION REQUISE', texte)
        self.assertIn('non transmise', texte)
        print("    CPE-13 noms nus -> cause DITE absente, jamais devinee, "
              "et pas d'ACTION REQUISE inventee")

    def test_CPE_14_le_rapport_signe_NE_DISPARAIT_PLUS(self):
        """⚠️⚠️ LA REGRESSION EN EUROS DE LECTEUR : l'Excel entier.

        C'est la mesure qui a ouvert le constat, devenue controle. Le cas
        ORDINAIRE -- une modalite one-hot constante -- suffisait a le vider.
        """
        from direction_non_vie.tarification.services.tarif_excel import (
            export_excel_a6,
        )
        base = {
            'success': True, 'statut_rag': 'VERT', 'classement': [],
            'modele_production': {}, 'backtest': {}, 'branche': 'auto',
            'audit_id': 'X', 'commentaire': '', 'courbes': {},
            'graphiques': {}, 'audit_trail': {}, 'exclusions_conformite': {},
            'controle_effet': {}, 'alertes_conformite': {},
            'alertes_modele': [], 'exclusions_cible': {},
            'colonnes_plan_manquantes': [], 'colonnes_exemptees_effet': {},
        }
        tailles = {}
        for etiquette, valeur in (('vide', {}), ('ordinaire', self._A3),
                                  ('grave', {'age': MOTIF_ECARTEE_FILTRE}),
                                  ('noms_nus', ['carburant_electrique'])):
            tailles[etiquette] = len(_sans_bruit(
                export_excel_a6, {**base, 'colonnes_plan_ecartees': valeur},
                'X'))
        for etiquette, taille in tailles.items():
            self.assertGreater(
                taille, 0,
                f"l'Excel A6 est VIDE sur le cas '{etiquette}' : le rapport "
                f"signe a disparu sur un logger.warning")
        print(f"    CPE-14 Excel A6 non vide sur les 4 formes : "
              f"{ {k: f'{v:,}' for k, v in tailles.items()} }")

    def test_CPE_15_ACTION_REQUISE_atteint_la_surface_par_le_TRAJET_REEL(self):
        """⚠️⚠️ LE CONTROLE QUI FERME `conformite/C16`.

        Il ne teste ni A3 seul ni la synthese seule : il rejoue **la
        transformation d'A6** entre les deux, puis lit le texte publie.
        *C'est le maillon que dix controles encadraient sans le traverser.*
        """
        a3 = {'age': MOTIF_ECARTEE_FILTRE}
        a4 = {'carburant_electrique': 'constante (variance nulle)'}
        traverse = fusionner_ecartees_amont(a3, a4)      # ce que A6 fait
        texte = synthese_colonnes_plan_ecartees(traverse, 'auto')
        self.assertIsNotNone(texte)
        self.assertIn(
            'ACTION REQUISE', texte,
            "un facteur DECLARE retire par un filtre amont ne se dit pas dans "
            "le rapport signe du chemin agent")
        self.assertIn('age', texte)
        self.assertIn('carburant_electrique', texte,
                      "le cas anodin a ete efface par le grave")
        # ⚠️ SECOND SENS : sans motif grave, aucune ACTION REQUISE.
        calme = synthese_colonnes_plan_ecartees(
            fusionner_ecartees_amont(a4), 'auto')
        self.assertNotIn('ACTION REQUISE', calme,
                         "l'alerte crie sur un portefeuille normal : un "
                         "avertissement permanent cesse d'etre lu")
        print("    CPE-15 ACTION REQUISE traverse A6 et atteint le texte ; "
              "silencieuse sur le cas ordinaire")


if __name__ == '__main__':
    unittest.main()
