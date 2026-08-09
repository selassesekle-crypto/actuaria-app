"""Tests F5 — un module importable ne configure pas le journal de son hôte.

⚠️ GATE : `py -m unittest discover -s core -t .` — voir test_frontiere_llm.py.

⚠️ ET C'EST POURQUOI CE FICHIER EST DANS `core/` ET PAS DANS `demos/`. Le
défaut mesuré vivait dans une démo, mais `demos/` et `scripts/` ne portent
AUCUN test et AUCUNE gate ne les découvre : le verrou y serait un test qui ne
tourne jamais. La règle, elle, est transverse — elle vaut pour les quatre
directions — donc elle se vérifie ici, où une gate la lit.

LE DÉFAUT, MESURÉ : `demos/pipeline_3lob_a1_a6_demo.py` réglait au niveau
module `actuaria` → ERROR et `actuaria.tarif.rapport` → CRITICAL. Or
`logging.getLogger` rend un objet DE PROCESSUS : le seul fait d'importer un
générateur de portefeuille depuis ce fichier éteignait le journal de
l'appelant. Mesuré avant correctif — `actuaria` NOTSET → ERROR,
`actuaria.tarif.rapport` NOTSET → CRITICAL, et sur ce dernier même les ERROR
passaient à la trappe : échec d'export Word, refus de narration, et
l'avertissement `[RELECTURE]` de la gouvernance.

CE QUE CE FICHIER NE COUVRE PAS, ET POURQUOI. Le relevé AST du dépôt donne 55
réglages de journal au niveau module. Trois familles, une seule est traitée :

  · ÉTEINDRE à l'import (`setLevel` ≥ ERROR)  : 2 sites → 0. VERROUILLÉ ICI.
  · `basicConfig(level=INFO)` à l'import      : 52 sites. Autre famille — le
    défaut y est « le premier importé gagne », pas l'extinction. Signalé.
  · `warnings.filterwarnings` à l'import      : 40 fichiers, dont tous les
    agents. Même forme, autre canal, et systémique. Signalé.

Les deux familles signalées sont hors périmètre de F5 : les traiter serait un
chantier à part, avec sa propre mesure.
"""
import ast
import os
import unittest
import warnings

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Les dossiers qu'on ne relit pas : ils ne sont pas à nous.
IGNORES = {'.git', '.venv', 'venv', '__pycache__', 'node_modules',
           '.ruff_cache', '.pytest_cache', 'site-packages', '.mypy_cache'}

#: Les niveaux qui ÉTEIGNENT : à partir d'ERROR, l'information courante est
#: perdue. En dessous, le réglage est un choix de verbosité, pas un silence.
SEUIL_EXTINCTION = 40  # logging.ERROR

NIVEAUX = {'CRITICAL': 50, 'FATAL': 50, 'ERROR': 40, 'WARNING': 30,
           'WARN': 30, 'INFO': 20, 'DEBUG': 10, 'NOTSET': 0}


def _niveau_vise(noeud):
    """Le niveau littéral d'un argument, ou None s'il est calculé."""
    if isinstance(noeud, ast.Attribute) and noeud.attr in NIVEAUX:
        return NIVEAUX[noeud.attr]
    if isinstance(noeud, ast.Name) and noeud.id in NIVEAUX:
        return NIVEAUX[noeud.id]
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, int):
        return noeud.value
    return None


def _cible(appel):
    """Le journal visé : son nom littéral, ou une étiquette lisible."""
    base = appel.func.value
    if (isinstance(base, ast.Call) and isinstance(base.func, ast.Attribute)
            and base.func.attr == 'getLogger'):
        if base.args and isinstance(base.args[0], ast.Constant):
            return str(base.args[0].value)
        return '(nom calculé)'
    if isinstance(base, ast.Name) and base.id == 'logging':
        return '(racine)'
    return '(variable)'


def extinctions_a_l_import(source, chemin='<memoire>'):
    """Les réglages qui ÉTEIGNENT un journal au SEUL fait d'importer.

    ⚠️ « Au niveau module » ne veut pas dire « colonne 0 » : un appel dans un
    `try`, un `with` ou un `if` de premier rang s'exécute aussi à l'import.
    On descend donc dans ces blocs, et on s'arrête à ce qui ne s'exécute PAS
    à l'import — le corps d'une fonction, d'une classe, et la garde
    `if __name__ == "__main__"`, qui est précisément le point d'entrée
    légitime.
    """
    trouves = []

    def descendre(corps, sous_garde_main):
        for n in corps:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
                continue
            if isinstance(n, ast.If):
                texte = ast.dump(n.test)
                garde = sous_garde_main or ('__name__' in texte
                                            and '__main__' in texte)
                descendre(n.body, garde)
                descendre(n.orelse, sous_garde_main)
                continue
            if isinstance(n, (ast.Try, ast.With, ast.AsyncWith)):
                for bloc in ('body', 'orelse', 'finalbody'):
                    descendre(getattr(n, bloc, []), sous_garde_main)
                for h in getattr(n, 'handlers', []):
                    descendre(h.body, sous_garde_main)
                continue
            if sous_garde_main:
                continue
            for sn in ast.walk(n):
                if not (isinstance(sn, ast.Call)
                        and isinstance(sn.func, ast.Attribute)):
                    continue
                if sn.func.attr == 'setLevel' and sn.args:
                    niveau = _niveau_vise(sn.args[0])
                    if niveau is not None and niveau >= SEUIL_EXTINCTION:
                        trouves.append((chemin, sn.lineno, _cible(sn), niveau))
                elif (sn.func.attr == 'disable'
                        and isinstance(sn.func.value, ast.Name)
                        and sn.func.value.id == 'logging'):
                    trouves.append((chemin, sn.lineno, '(tout)',
                                    _niveau_vise(sn.args[0]) if sn.args
                                    else SEUIL_EXTINCTION))

    descendre(ast.parse(source).body, False)
    return trouves


def _fichiers_du_depot():
    for dossier, sousdossiers, fichiers in os.walk(RACINE):
        sousdossiers[:] = [d for d in sousdossiers if d not in IGNORES]
        for nom in fichiers:
            if nom.endswith('.py'):
                yield os.path.join(dossier, nom)


class F5_LeDetecteurLuiMeme(unittest.TestCase):
    """⚠️ TÉMOIN POSITIF, ET IL N'EST PAS DÉCORATIF. Un test qui balaie le
    dépôt et trouve zéro passe aussi bien quand le détecteur est cassé que
    quand le dépôt est sain. On lui plante donc de vrais défauts, et on
    vérifie qu'il les voit — sinon le verrou ci-dessous ne verrouille rien."""

    def test_il_voit_les_formes_qui_eteignent(self):
        cas = [
            ('logging.getLogger("a").setLevel(logging.ERROR)', 'ERROR direct'),
            ('logging.getLogger("a").setLevel(logging.CRITICAL)', 'CRITICAL'),
            ('logging.getLogger("a").setLevel(40)', 'niveau numerique'),
            ('import logging\nlogging.disable(logging.ERROR)', 'disable'),
            (('try:\n    logging.getLogger("a").setLevel(logging.ERROR)\n'
              'except Exception:\n    pass'),
             'dans un try de premier rang'),
            ('if True:\n    logging.getLogger("a").setLevel(logging.ERROR)',
             'dans un if de premier rang'),
        ]
        for source, nom in cas:
            with self.subTest(forme=nom):
                self.assertTrue(extinctions_a_l_import(source),
                                f'forme non detectee : {nom}')
        print(f'    OK temoin : les {len(cas)} formes qui eteignent'
              ' sont vues')

    def test_il_ne_crie_pas_sur_ce_qui_est_legitime(self):
        """⚠️ L'AUTRE SENS COMPTE AUTANT : un détecteur qui hurle sur les
        formes correctes ferait supprimer des silences légitimes."""
        cas = [
            ('def main():\n    logging.getLogger("a").setLevel(logging.ERROR)',
             'dans une fonction'),
            (('if __name__ == "__main__":\n'
              '    logging.getLogger("a").setLevel(logging.ERROR)'),
             'sous la garde __main__'),
            ('logging.basicConfig(level=logging.INFO)', 'basicConfig INFO'),
            ('logging.getLogger("a").setLevel(logging.DEBUG)',
             'verbosite, pas extinction'),
            ('class C:\n    logging.getLogger("a").setLevel(logging.ERROR)',
             'dans une classe'),
        ]
        for source, nom in cas:
            with self.subTest(forme=nom):
                self.assertEqual(extinctions_a_l_import(source), [],
                                 f'faux positif : {nom}')
        print(f'    OK temoin : les {len(cas)} formes legitimes'
              ' sont laissees')


class F5_LeDepotEntier(unittest.TestCase):
    """F5 — aucun module du dépôt n'éteint un journal au seul fait d'être
    importé. Le verrou porte sur TOUT le dépôt, pas sur la démo seule : le
    défaut pouvait renaître ailleurs, y compris dans le lanceur."""

    def test_aucun_module_n_eteint_un_journal_a_l_import(self):
        coupables = []
        lus = 0
        for chemin in _fichiers_du_depot():
            try:
                with open(chemin, encoding='utf-8') as f:
                    source = f.read()
            except (OSError, UnicodeDecodeError):
                continue
            # ⚠️ ON MET EN SOURDINE LES *SyntaxWarning* DE `ast.parse`, ET
            # UNIQUEMENT ICI. Un fichier du dépôt en émet un —
            # `direction_sante_prevoyance/services/m_rapport_tarif_prev.py`
            # ligne 217 porte la séquence d'échappement invalide « \\  » (elle
            # deviendra une erreur dans une version future de Python). C'est
            # un vrai défaut, SIGNALÉ ET NON TRAITÉ : il est dans une autre
            # direction et n'a rien à voir avec F5. Mais ce test n'est pas son
            # messager : il le relayerait à chaque passage de la gate, où on
            # le prendrait pour une panne d'ici.
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', SyntaxWarning)
                    trouves = extinctions_a_l_import(
                        source,
                        os.path.relpath(chemin, RACINE).replace('\\', '/'))
            except SyntaxError:
                continue
            lus += 1
            coupables.extend(trouves)
        self.assertGreater(lus, 200,
                           'le balayage n a presque rien lu : verifier RACINE')
        self.assertEqual(
            coupables, [],
            'un module eteint un journal a l import :\n' + '\n'.join(
                f'  {f}:{ligne}  -> {c} mis a {n}'
                for f, ligne, c, n in coupables))
        print(f'    OK F5 : {lus} modules relus, 0 extinction a l import')


class F5_LaDemoQuiPortaitLeDefaut(unittest.TestCase):
    """F5 — le cas nommé, gardé séparément du balayage général : si la démo
    reprenait l'habitude, on saurait lequel des deux verrous a cédé."""

    CHEMIN = os.path.join(RACINE, 'demos', 'pipeline_3lob_a1_a6_demo.py')

    def test_la_demo_regle_ses_journaux_dans_une_fonction(self):
        with open(self.CHEMIN, encoding='utf-8') as f:
            source = f.read()
        self.assertEqual(extinctions_a_l_import(source, 'demo'), [])
        # et les reglages EXISTENT toujours : on a deplace, pas supprime.
        arbre = ast.parse(source)
        dans_fonction = [
            n for n in ast.walk(arbre)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            for sn in ast.walk(n)
            if isinstance(sn, ast.Call) and isinstance(sn.func, ast.Attribute)
            and sn.func.attr == 'setLevel']
        self.assertTrue(dans_fonction,
                        'le silence de la demo a disparu au lieu de bouger')
        print('    OK F5-demo : le silence est dans une fonction, et il '
              'existe encore')


if __name__ == '__main__':
    unittest.main(verbosity=2)
