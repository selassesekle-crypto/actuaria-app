"""UNE COLLISION DE MAPPING NE S'APPLIQUE PAS -- point (4) du chantier.

`a1._appliquer_mapping_client` renommait TOUJOURS. Le socle sait pourtant
depuis toujours qu'un renommage creant deux colonnes de meme nom est
incoherent (`valider_mapping` leve), et depuis le lot 11 le diagnostic VOIT
la collision -- il la signalait sans l'empecher.

  ***Mesure du 08/09/2026, les DEUX formes de collision*** -- deux sources
  vers une cible, et une cible qui coincide avec une colonne deja presente :
  A1 rendait `['age', 'age', 'autre']` avec `applique=True`.

Une colonne en double n'est pas une donnee ambigue : `df['age']` rend alors
un DataFrame la ou tout l'aval attend une Series, et A2/A3 tarifent sur ce
que l'ordre des colonnes decide.

⚠️⚠️ LA REGLE EST ASYMETRIQUE, ET C'EST L'ARBITRAGE RENDU :
  · une CIBLE INCONNUE du plan se SIGNALE et s'applique -- elle produit une
    colonne que le plan ignore, pas une ambiguite ;
  · une COLLISION se REFUSE.
*Deux incoherences, deux dispositions* -- c'est precisement ce que
`diagnostiquer_mapping` rend possible en ne levant pas lui-meme.

⚠️ ET A1 NE LEVE PAS VERS SON APPELANT. La levee remonte au `try` de
`run()`, qui rend le contrat de sortie COMPLET (`success=False`, `erreur`
nommee, dix-sept cles). Un agent qui remonte une exception nue casse le
contrat que `CS-1` garde.

  MA-1  une collision n'est PAS appliquee, aucune colonne en double ;
  MA-2  et A1 rend son CONTRAT DE SORTIE complet, pas une exception nue ;
  MA-3  SECOND SENS : une cible inconnue est appliquee ET signalee ;
  MA-4  SECOND SENS : sans mapping, rien ne change ;
  MA-5  la levee est HORS du bloc qui declare `echec_chargement` ;
  MA-6  la regle vient du SOCLE, elle n'est pas recopiee dans A1.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""

from __future__ import annotations

import ast
import json
import os
import pathlib
import sys
import tempfile
import unittest

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))
for _c in (_RACINE, _ICI):
    if _c not in sys.path:
        sys.path.insert(0, _c)

import pandas as pd

from core.mapping_client import MappingIncoherent
from core.plan_tarifaire import PlanTarifaire
from direction_non_vie.tarification.a1_ingestion.agent import (
    GABARIT_SORTIE,
    AgentA1Ingestion,
)

_A1 = pathlib.Path(_ICI) / 'a1_ingestion' / 'agent.py'


def _MOT(nom: str) -> str:
    """Le nom d'une colonne cherche COMME UN MOT, jamais en sous-chaine.

    ⚠️⚠️ TROUVE PAR LE SCEAU, PAS PAR LA RELECTURE. La premiere version de
    `MA-1` et `MA-2` faisait `assertIn('age', message)` -- or la colonne du
    plan s'appelle `age`, et `age` est une sous-chaine de « renommage », de
    « Mapping » et de « message ». Le plant qui RETIRAIT le nom du message
    laissait donc `MA-2` VERTE : le controle passait pour la mauvaise
    raison. *Un releve par symbole attrape l'homonyme, meme a l'interieur
    d'un mot.* Voir [releve-symbole-vs-prose].
    """
    import re as _re
    return r'(?<![\w])' + _re.escape(nom) + r'(?![\w])'


def _plan():
    return PlanTarifaire.depuis_yaml(
        os.path.join(_RACINE, 'plans', 'auto.yaml'))


def _appliquer(colonnes, mapping, plan=None):
    """Le SITE DE PRODUCTION, appele tel quel, mapping en dossier temporaire.

    ⚠️ Jamais `config/` du depot."""
    df = pd.DataFrame({c: [1.0, 2.0, 3.0] for c in colonnes})
    a1 = AgentA1Ingestion.__new__(AgentA1Ingestion)
    with tempfile.TemporaryDirectory() as tmp:
        (pathlib.Path(tmp) / 'demo_mapping.json').write_text(
            json.dumps(mapping, ensure_ascii=False), encoding='utf-8')
        a1.config_path_dir = pathlib.Path(tmp)
        return a1._appliquer_mapping_client(df, 'demo', plan=plan)


class TestCollisionDeMappingRefusee(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.plan = _plan()
        cls.att = sorted(cls.plan.colonnes_attendues())

    def test_MA1_une_collision_n_est_PAS_appliquee(self):
        """⚠️⚠️ LES DEUX FORMES, parce qu'elles n'ont pas la meme cause : deux
        sources qui visent la meme cible, et une cible qui coincide avec une
        colonne DEJA presente. Mesure avant correctif : les deux rendaient
        `['age', 'age', 'autre']`."""
        cas = (
            ('deux sources vers une cible',
             ['SRC_A', 'SRC_B', 'autre'],
             {'SRC_A': self.att[0], 'SRC_B': self.att[0]}),
            ('la cible existe deja',
             ['SRC_A', self.att[0], 'autre'],
             {'SRC_A': self.att[0]}),
        )
        for nom, cols, mp in cas:
            with self.subTest(forme=nom):
                with self.assertRaises(MappingIncoherent) as leve:
                    _appliquer(cols, mp, self.plan)
                message = str(leve.exception)
                self.assertRegex(
                    message, _MOT(self.att[0]),
                    'la collision n est pas NOMMEE dans le message')
                self.assertIn('double', message.lower())
        print('    MA-1 les deux formes de collision sont refusees')

    def test_MA2_A1_rend_son_CONTRAT_DE_SORTIE_pas_une_exception_nue(self):
        """⚠️⚠️ LE POINT QUI DECIDE. Un agent qui remonte une exception nue
        casse le contrat que `CS-1` garde : ses consommateurs attendent un
        dict, pas un `raise`. La levee doit etre RATTRAPEE par `run()` et
        convertie en sortie complete."""
        df = pd.DataFrame({c: [1.0, 2.0, 3.0]
                           for c in ['SRC_A', 'SRC_B', 'autre']})
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / 'demo_mapping.json').write_text(
                json.dumps({'SRC_A': self.att[0], 'SRC_B': self.att[0]}),
                encoding='utf-8')
            a1 = AgentA1Ingestion(audit_path=tmp, verbose=False)
            a1.config_path_dir = pathlib.Path(tmp)
            sortie = a1.run(branche='non_vie', sous_branche='auto',
                            dataframe=df, plan=self.plan, client_id='demo')
        self.assertIsInstance(sortie, dict,
                              'A1 a remonte une exception au lieu de rendre '
                              'son contrat de sortie')
        self.assertFalse(sortie.get('success'))
        self.assertEqual(
            sorted(sortie), sorted(GABARIT_SORTIE),
            f'contrat de sortie AMPUTE sur ce chemin : manquantes '
            f'{sorted(set(GABARIT_SORTIE) - set(sortie))}')
        self.assertRegex(
            str(sortie.get('erreur') or ''), _MOT(self.att[0]),
            "l'erreur publiee ne nomme pas la colonne en collision")
        print(f'    MA-2 contrat complet ({len(sortie)} cles), success=False, '
              f'erreur nommee')

    def test_MA3_SECOND_SENS_une_cible_inconnue_est_appliquee_et_signalee(self):
        """⚠️⚠️ SANS CE SENS, refuser TOUTE incoherence passerait MA-1 -- et
        on aurait remplace un renommage trop permissif par un blocage trop
        large. Une cible inconnue du plan ne cree AUCUNE ambiguite."""
        df, info = _appliquer(['SRC_A', 'autre'],
                              {'SRC_A': self.att[0] + '_FAUTE'}, self.plan)
        self.assertTrue(info['applique'], 'la cible inconnue a ete REFUSEE : '
                                         'le blocage est trop large')
        self.assertIn(self.att[0] + '_FAUTE', list(df.columns))
        self.assertEqual(len(set(df.columns)), len(df.columns))
        rap = info.get('rapport')
        self.assertIsNotNone(rap)
        self.assertIn(self.att[0] + '_FAUTE', rap.cibles_inconnues_du_plan)
        print('    MA-3 cible inconnue : appliquee ET signalee')

    def test_MA4_SECOND_SENS_sans_collision_rien_ne_change(self):
        """⚠️ Le cas de la quasi-totalite des dossiers."""
        df, info = _appliquer(['SRC_A', 'autre'],
                              {'SRC_A': self.att[0]}, self.plan)
        self.assertTrue(info['applique'])
        self.assertEqual(list(df.columns), [self.att[0], 'autre'])
        self.assertIsNone(info.get('collisions_bloquantes'))
        # ⚠️ Et sans plan du tout : aucun diagnostic possible, aucun blocage.
        _, info2 = _appliquer(['SRC_A', 'SRC_B'],
                              {'SRC_A': self.att[0], 'SRC_B': self.att[0]})
        self.assertTrue(info2['applique'],
                        'sans plan signe, A1 ne peut RIEN diagnostiquer : il '
                        'ne doit pas bloquer sur une regle qu il ne peut pas '
                        'appliquer')
        print('    MA-4 nominal inchange, et sans plan A1 ne bloque pas')

    def test_MA5_la_levee_est_HORS_du_bloc_qui_declare_echec_chargement(self):
        """⚠️⚠️ UN GARDE-FOU POSE DANS LE BLOC QUI RATTRAPE TOUT NE GARDE
        RIEN. Levee a l'interieur du `try`, la collision serait avalee par le
        `except Exception` qui declare `echec_chargement` : elle se lirait
        comme un fichier ILLISIBLE, et A1 continuerait avec un df non
        renomme. Mesure : `echec_chargement` doit rester None."""
        with self.assertRaises(MappingIncoherent):
            _appliquer(['SRC_A', 'SRC_B', 'autre'],
                       {'SRC_A': self.att[0], 'SRC_B': self.att[0]},
                       self.plan)
        # ⚠️ Par AST : le `raise` n'est dans AUCUN `try` de la methode.
        arbre = ast.parse(_A1.read_text(encoding='utf-8'))
        methode = next(n for n in ast.walk(arbre)
                       if isinstance(n, ast.FunctionDef)
                       and n.name == '_appliquer_mapping_client')
        dans_un_try = set()
        for noeud in ast.walk(methode):
            if isinstance(noeud, ast.Try):
                for sous in ast.walk(noeud):
                    if isinstance(sous, ast.Raise):
                        dans_un_try.add(sous.lineno)
        tous = {n.lineno for n in ast.walk(methode)
                if isinstance(n, ast.Raise)}
        self.assertTrue(tous, 'aucune levee dans la methode')
        self.assertEqual(
            tous & dans_un_try, set(),
            f'levee(s) a l interieur d un `try` de la methode : '
            f'{sorted(tous & dans_un_try)} -- elles seraient avalees')
        print(f'    MA-5 la levee (l. {sorted(tous)}) est hors de tout `try`')

    def test_MA6_la_regle_vient_du_SOCLE_elle_n_est_pas_recopiee(self):
        """⚠️ Recopier le calcul de collision dans A1 aurait produit deux jeux
        de regles qui divergent -- le defaut que ce chantier ferme partout.
        A1 LIT `rapport.collisions` ; il ne le recalcule pas."""
        texte = _A1.read_text(encoding='utf-8')
        self.assertIn("getattr(_rap, 'collisions', ())", texte,
                      'A1 ne lit plus les collisions du rapport du socle')
        # ⚠️⚠️ LES MOTIFS INTERDITS SONT CEUX DU SOCLE, PAS DES HOMONYMES.
        # Mon premier jet interdisait « doublons = » : A1 en porte quatre
        # occurrences qui comptent les LIGNES en double (`df.duplicated`), un
        # tout autre sujet. *Un releve par symbole attrape l'homonyme* --
        # voir [releve-symbole-vs-prose]. On cherche donc les expressions
        # EXACTES du calcul de collision de `diagnostiquer_mapping`.
        for interdit in ('finaux.count(', 'cibles.count(',
                         'for n in finaux', 'set(doublons)'):
            with self.subTest(interdit=interdit):
                self.assertNotIn(
                    interdit, texte,
                    f'A1 recalcule les collisions ({interdit}) : deux jeux de '
                    f'regles qui divergeront')
        print('    MA-6 A1 lit la regle du socle, il ne la recopie pas')


if __name__ == '__main__':
    unittest.main(verbosity=2)
