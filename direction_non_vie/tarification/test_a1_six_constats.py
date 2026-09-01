"""Controles positifs -- `a1` : les six derniers constats de la zone.

═══ ⛔⛔ `C2` -- LE GARDE-FOU GARDAIT L'ARGUMENT, PAS L'ACTE ═══

L'en-tete promet << Empeche qu'un portefeuille Vie ou Sante soit ingere par
erreur >>. Mesure du 01/09 : un fichier place dans `data/vie/` **est charge**
sous `branche='non_vie'`. Le garde-fou de `run()` ne voit qu'une CHAINE ; le
chargeur, lui, ENUMERAIT NOMMEMENT les dossiers exclus :

    branches_ordre = [branche] + [b for b in ['non_vie', 'vie',
                                              'sante_prevoyance'] ...]

> *La garde portait sur un argument, l'ingestion porte sur un chemin.*

La liste explorée DERIVE desormais de `BRANCHES_SUPPORTEES`, et le refus
distingue deux etats que l'ancien message confondait : **<< absent >> et
<< present hors perimetre >> ne sont pas la meme chose.**

═══ ⛔⛔ `C8` -- LA TRACE ACPR DISPARAISSAIT SANS UN MOT, ET ILS ETAIENT SIX ═══

Dossier inecrivable : aucun fichier, `success=True`, `erreur=None`,
`alertes=[]`. Le dict `audit_trail` reste en memoire ; c'est la trace
PERSISTEE qui s'evapore.

⚠️ LE CONSTAT N'EN NOMMAIT QU'UN. Releve par AST sur les sept
`_sauvegarder_audit` du depot : **cinq avalent l'echec par `except: pass`**
(a1, a3, a4, a5, a6), deux le passent au `logger` (a2, a7) -- et **aucun ne le
fait remonter dans le resultat signe**. Un `logger.warning` n'est pas dans le
livrable que l'actuaire signe.

Le patron applique est celui que `a6` porte DEJA, arbitre, pour son archive :
*<< L'echec REMONTE dans le resultat, il n'est pas avale. >>* `rapport` est
dans la signature des six et voyage jusqu'au resultat : l'echec y est nomme.

⚠️ A7 N'EST PAS TOUCHE -- hors assiette de gate, et il porte les oracles.

═══ ⛔ `C7` + `a2/C16` -- ET QUATRE JUMEAUX QUE PERSONNE N'AVAIT COMPTES ═══

Instancier A1 creait `/tmp/actuaria/{audit,config}`. Le constat jumeau
`a2/C16` disait la meme chose de A2. **Mesure : a3, a4, a5 et a6 le font
aussi.** Six agents, deux constats numerotes.

> *Construire un objet n'est pas ecrire un fichier.* Les dossiers sont
> desormais crees PAR CELUI QUI ECRIT, juste avant d'ecrire.

═══ LES TROIS AUTRES ═══

| constat | ce qui etait annonce | ce qui est |
|---|---|---|
| `C5` | `SYNONYMES_COLONNES` propre | `id_police` et `nb_sin` en double |
| `C9` | `verifier_tous_fichiers` | 1 definition, 0 appel -- et 10 fichiers Vie/Sante annonces |
| `C10` | << 7 tests >> | 13 methodes |

⚠️ `C5` : les deux doublons sont INTRA-liste, donc sans effet -- mesure faite
AVANT de retirer. `A1-4` verifie desormais les deux formes : intra-liste ET
inter-cles, la seconde etant celle qui ferait taire un renommage.
"""

from __future__ import annotations

import ast
import datetime
import glob
import logging
import pathlib
import tempfile
import unittest

import pandas as pd

from direction_non_vie.tarification.a1_ingestion import agent as _a1mod
from direction_non_vie.tarification.a1_ingestion.agent import (
    BRANCHES_SUPPORTEES,
    SYNONYMES_COLONNES,
    AgentA1Ingestion,
)
from direction_non_vie.tarification.a2_preprocessing.agent import (
    AgentA2Preprocessing,
)
from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
from direction_non_vie.tarification.a5_deep_learning.agent import (
    AgentA5DeepLearning,
)
from direction_non_vie.tarification.a6_comparaison.agent import (
    AgentA6Comparaison,
)

_SOURCE = pathlib.Path(_a1mod.__file__).read_text(encoding='utf-8')
_RACINE = pathlib.Path(_a1mod.__file__).parents[1]

# Les six agents de tarification, avec la fabrique qui les construit dans un
# dossier NEUF. La cle est la zone : un message d'echec doit nommer le coupable.
_SIX = {
    'a1': lambda d: AgentA1Ingestion(base_path=str(d / 'b'),
                                     audit_path=str(d / 'audit'),
                                     config_path=str(d / 'cfg'), verbose=False),
    'a2': lambda d: AgentA2Preprocessing(models_path=str(d / 'm'),
                                         audit_path=str(d / 'audit'),
                                         verbose=False),
    'a3': lambda d: AgentA3GLM(models_path=str(d / 'm'),
                               audit_path=str(d / 'audit'), verbose=False),
    'a4': lambda d: AgentA4ML(models_path=str(d / 'm'),
                              audit_path=str(d / 'audit'), verbose=False),
    'a5': lambda d: AgentA5DeepLearning(models_path=str(d / 'm'),
                                        audit_path=str(d / 'audit'),
                                        verbose=False),
    'a6': lambda d: AgentA6Comparaison(models_path=str(d / 'm'),
                                       audit_path=str(d / 'audit'),
                                       verbose=False),
}
_MODULES = {
    'a1': 'a1_ingestion', 'a2': 'a2_preprocessing', 'a3': 'a3_glm',
    'a4': 'a4_ml', 'a5': 'a5_deep_learning', 'a6': 'a6_comparaison',
}
# Ce que chaque `_sauvegarder_audit` lit dans `rapport` -- un dict trop pauvre
# leverait un KeyError et le controle mesurerait la mauvaise chose.
_RAPPORT = {
    'etapes': [], 'alertes': [],
    'nb_lignes_debut': 10, 'nb_cols_debut': 3,
}


def _appeler_sauvegarde(zone, agent, rapport):
    """Appelle `_sauvegarder_audit` avec la signature reelle de la zone."""
    t0 = datetime.datetime.now(datetime.timezone.utc)
    if zone == 'a1':
        agent._sauvegarder_audit('ID_TEST', 'auto', rapport,
                                 {'score_global': 90, 'nb_lignes': 10},
                                 'VERT', 'hash', t0, None)
    else:
        agent._sauvegarder_audit('ID_TEST', 'auto', rapport, 'VERT', t0)


_CLASSES = {
    'a1': 'AgentA1Ingestion', 'a2': 'AgentA2Preprocessing',
    'a3': 'AgentA3GLM', 'a4': 'AgentA4ML',
    'a5': 'AgentA5DeepLearning', 'a6': 'AgentA6Comparaison',
}


def _source(zone):
    return (_RACINE / _MODULES[zone] / 'agent.py').read_text(encoding='utf-8')


def _methode(zone, nom):
    """La methode de LA CLASSE D'AGENT -- pas la premiere venue du fichier.

    ⚠️⚠️ `a4` et `a5` portent TROIS `__init__` chacun (`_GLMWalkForward`,
    `_ModeleFrequenceExposition`, `CANNModel`, `TabNetSimple`, puis l'agent).
    Un releve qui prend le premier `__init__` rencontre par `ast.walk`
    surveillait DEUX CLASSES INTERNES en croyant surveiller deux agents --
    2 zones sur 6 sans garde, en silence. **C'est le sceau qui l'a demasque**,
    en plantant la violation AU BON ENDROIT : le plant tombait, le controle
    ne bronchait pas. *Un controle qui regarde a cote ne peut pas echouer.*
    """
    for c in ast.walk(ast.parse(_source(zone))):
        if isinstance(c, ast.ClassDef) and c.name == _CLASSES[zone]:
            for f in c.body:
                if isinstance(f, ast.FunctionDef) and f.name == nom:
                    return f
    return None


class TestA1SixConstats(unittest.TestCase):
    """Six constats de la zone `a1`, plus le balayage de leurs jumeaux."""

    def setUp(self):
        self._bruit = logging.root.manager.disable
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(self._bruit)

    # ── `a1/C2` — le perimetre garde l'ACTE ───────────────────────────────────

    def test_A1_1_le_chargeur_ne_nomme_plus_les_branches_exclues(self):
        """`a1/C2` : la liste exploree DERIVE de BRANCHES_SUPPORTEES."""
        fn = _methode('a1', '_charger_fichier')
        self.assertIsNotNone(fn, '_charger_fichier introuvable')
        litteraux = {n.value for n in ast.walk(fn)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        for interdit in ('vie', 'sante_prevoyance'):
            self.assertNotIn(
                interdit, litteraux,
                f"_charger_fichier nomme encore '{interdit}' : la liste des "
                f"dossiers explores doit DERIVER de BRANCHES_SUPPORTEES, "
                f"jamais etre reecrite a la main.")
        noms = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        self.assertIn('BRANCHES_SUPPORTEES', noms,
                      '_charger_fichier ne consulte plus BRANCHES_SUPPORTEES')

    def test_A1_2_LE_TEST_QUI_FERME_un_fichier_Vie_est_REFUSE(self):
        """`a1/C2` : par EXECUTION -- data/vie/ n'est plus ingere."""
        d = pathlib.Path(tempfile.mkdtemp())
        (d / 'vie').mkdir()
        pd.DataFrame({'x': [1, 2, 3]}).to_csv(d / 'vie' / 'pf.csv', index=False)
        a1 = AgentA1Ingestion(base_path=str(d), audit_path=str(d / 'a'),
                              config_path=str(d / 'c'), verbose=False)
        with self.assertRaises(FileNotFoundError) as ctx:
            a1._charger_fichier('pf.csv', 'non_vie')
        msg = str(ctx.exception)
        self.assertIn('HORS PÉRIMÈTRE', msg,
                      "le refus doit DIRE que le fichier est la mais hors "
                      "perimetre -- << non trouve >> ferait chercher un "
                      f"fichier qui existe. Message : {msg}")
        self.assertIn('vie', msg, 'le refus ne nomme pas le dossier trouve')

    def test_A1_3_le_perimetre_ne_bloque_pas_le_Non_Vie(self):
        """`a1/C2` : le filet ne doit pas etre trop large non plus."""
        d = pathlib.Path(tempfile.mkdtemp())
        (d / 'non_vie').mkdir()
        pd.DataFrame({'x': [1, 2]}).to_csv(d / 'non_vie' / 'ok.csv', index=False)
        a1 = AgentA1Ingestion(base_path=str(d), audit_path=str(d / 'a'),
                              config_path=str(d / 'c'), verbose=False)
        self.assertEqual(len(a1._charger_fichier('ok.csv', 'non_vie')), 2)
        # La branche refusee est DERIVEE de la constante, pas ecrite a la main :
        # le jour ou le perimetre change, le controle change avec lui.
        hors = next(b for b in ('vie', 'sante_prevoyance', 'epargne')
                    if b not in BRANCHES_SUPPORTEES)
        with self.assertRaises(ValueError):
            a1._charger_fichier('ok.csv', hors)

    # ── `a1/C5` — les synonymes ───────────────────────────────────────────────

    def test_A1_4_aucun_synonyme_en_double_intra_liste_NI_inter_cles(self):
        """`a1/C5`, elargi : le doublon INTER-cles est le vrai danger."""
        for canonique, synonymes in SYNONYMES_COLONNES.items():
            self.assertEqual(
                len(synonymes), len(set(synonymes)),
                f"'{canonique}' porte un synonyme en double : "
                f"{[s for s in set(synonymes) if synonymes.count(s) > 1]}")
        # ⚠️ LA MOITIE INTER-CLES A DEJA UN PROPRIETAIRE :
        # `test_vocabulaire_echeance.py` la tient sur toute la table. Elle est
        # REDITE ici pour que `a1/C5` reste epingle si ce voisin change --
        # et c'est DIT, plutot que de laisser croire a un controle neuf.
        vus = {}
        for canonique, synonymes in SYNONYMES_COLONNES.items():
            for s in synonymes:
                if s in vus and vus[s] != canonique:
                    self.fail(
                        f"'{s}' est synonyme de '{vus[s]}' ET de "
                        f"'{canonique}' : un renommage silencieux vers la "
                        f"DERNIERE cle rencontree.")
                vus[s] = canonique

    # ── `a1/C7` + `a2/C16` + quatre jumeaux — construire n'ecrit pas ──────────

    def test_A1_5_aucun_init_des_six_agents_n_appelle_mkdir(self):
        """`a1/C7` `a2/C16` : par AST, sur les SIX -- pas seulement les deux."""
        for zone in _SIX:
            init = _methode(zone, '__init__')
            self.assertIsNotNone(init, f'{zone} : __init__ introuvable')
            # ⚠️ `.mkdir` n'est pas la seule forme du FAIT : `os.makedirs` et
            # `os.mkdir` creent le meme dossier. Un releve par une SEULE
            # forme syntaxique laisserait la porte ouverte a cote.
            fautifs = [f'{getattr(n.func, "attr", "?")} l.{n.lineno}'
                       for n in ast.walk(init) if isinstance(n, ast.Call)
                       and getattr(n.func, 'attr', '') in ('mkdir', 'makedirs')]
            self.assertEqual(
                fautifs, [],
                f"{zone} : __init__ appelle mkdir ({fautifs}). Construire un "
                f"agent ne doit pas ecrire sur le disque -- le dossier est "
                f"cree par celui qui ECRIT.")

    def test_A1_6_LE_TEST_QUI_FERME_construire_ne_cree_rien(self):
        """`a1/C7` `a2/C16` : par EXECUTION, sur les six."""
        for zone, fabrique in _SIX.items():
            d = pathlib.Path(tempfile.mkdtemp())
            fabrique(d)
            nes = sorted(p.name for p in d.glob('*'))
            self.assertEqual(
                nes, [],
                f"{zone} : construire l'agent a cree {nes} dans un dossier "
                f"neuf.")

    def test_A1_7_mais_celui_qui_ECRIT_cree_encore_son_dossier(self):
        """Anti-regression : la creation paresseuse doit fonctionner."""
        for zone, fabrique in _SIX.items():
            d = pathlib.Path(tempfile.mkdtemp())
            agent = fabrique(d)
            _appeler_sauvegarde(zone, agent, dict(_RAPPORT))
            self.assertTrue(
                (d / 'audit').exists(),
                f"{zone} : le dossier d'audit n'est plus cree a l'ecriture.")
            self.assertEqual(
                sorted(p.name for p in (d / 'audit').glob('*.json')),
                ['ID_TEST.json'],
                f"{zone} : l'audit trail n'a pas ete ecrit.")

    # ── `a1/C8` + cinq jumeaux — la trace perdue est nommee ───────────────────

    def test_A1_8_aucun_sauvegarder_audit_n_avale_l_echec(self):
        """`a1/C8` : par AST, sur les six -- `except: pass` est interdit."""
        for zone in _SIX:
            fn = _methode(zone, '_sauvegarder_audit')
            self.assertIsNotNone(fn, f'{zone} : _sauvegarder_audit introuvable')
            for h in ast.walk(fn):
                if isinstance(h, ast.ExceptHandler):
                    muet = all(isinstance(x, ast.Pass) for x in h.body)
                    self.assertFalse(
                        muet,
                        f"{zone} l.{h.lineno} : l'echec de persistance de "
                        f"l'audit trail est avale par un `pass`.")

    def test_A1_9_LE_TEST_QUI_FERME_l_echec_est_NOMME_dans_le_resultat(self):
        """`a1/C8` : par EXECUTION, sur les six -- l'alerte remonte."""
        for zone, fabrique in _SIX.items():
            d = pathlib.Path(tempfile.mkdtemp())
            # Un FICHIER a la place du dossier : mkdir echoue, l'ecriture aussi.
            (d / 'audit').write_text('obstacle', encoding='utf-8')
            agent = fabrique(d)
            rapport = dict(_RAPPORT, alertes=[])
            _appeler_sauvegarde(zone, agent, rapport)
            self.assertEqual(
                len(rapport['alertes']), 1,
                f"{zone} : l'audit trail n'a pas ete persiste et le resultat "
                f"n'en porte AUCUNE alerte -- alertes={rapport['alertes']}")
            self.assertIn(
                'NON persisté', rapport['alertes'][0],
                f"{zone} : l'alerte ne dit pas que la trace n'est pas ecrite.")

    def test_A1_10_le_mapping_suggere_non_ecrit_est_dit(self):
        """Meme forme, autre artefact : la suggestion de mapping."""
        d = pathlib.Path(tempfile.mkdtemp())
        (d / 'cfg').write_text('obstacle', encoding='utf-8')
        a1 = AgentA1Ingestion(base_path=str(d / 'b'), audit_path=str(d / 'a'),
                              verbose=False)
        # ⚠️ `config_path` designe le FICHIER de config, pas le dossier :
        # `config_path_dir` derive du CONTENU du JSON charge. Le poser ici
        # evite une repro infidele -- et evite d'ecrire dans /tmp/actuaria.
        a1.config_path_dir = d / 'cfg'
        _, info = a1._appliquer_mapping_client(
            pd.DataFrame({'num_police': [1], 'claimnb': [0]}), 'client_test')
        self.assertIn(
            'NON ÉCRIT', str(info.get('mapping_source', '')),
            "la suggestion de mapping n'a pas pu etre ecrite et le rapport "
            f"n'en dit rien : {info}")

    # ── `a1/C9` et `a1/C10` ───────────────────────────────────────────────────

    def test_A1_11_verifier_tous_fichiers_n_existe_plus(self):
        """`a1/C9` : 1 definition, 0 appel, et un inventaire hors perimetre."""
        self.assertFalse(
            hasattr(_a1mod, 'verifier_tous_fichiers'),
            'verifier_tous_fichiers est de retour dans le module A1.')
        defs = [n.name for n in ast.walk(ast.parse(_SOURCE))
                if isinstance(n, ast.FunctionDef)]
        self.assertNotIn('verifier_tous_fichiers', defs)
        for fichier in ('contrats_vie_indiv_70k', 'contrats_sante_coll_70k',
                        'sinistres_sante_prev'):
            self.assertNotIn(
                fichier, _SOURCE,
                f"A1 nomme encore le fichier hors perimetre '{fichier}'.")

    def test_A1_12_aucun_en_tete_de_la_zone_n_annonce_un_compte(self):
        """`a1/C10` : un compte dans un en-tete perime en silence."""
        import re
        motif = re.compile(r'\b\d+\s+tests?\b', re.IGNORECASE)
        for chemin in glob.glob(str(_RACINE / 'a1_ingestion' / '*.py')):
            tete = pathlib.Path(chemin).read_text(
                encoding='utf-8').split('"""')[1:2]
            if not tete:
                continue
            trouve = motif.search(tete[0])
            self.assertIsNone(
                trouve,
                f'{pathlib.Path(chemin).name} annonce '
                f'<< {trouve.group(0) if trouve else ""} >> dans son en-tete.')


if __name__ == '__main__':
    unittest.main(verbosity=2)
