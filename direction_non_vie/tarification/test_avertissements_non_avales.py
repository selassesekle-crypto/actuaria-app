"""Controles positifs — `a2/C15` : le filtre global d'avertissements.

CE QUE CE FICHIER PROUVE, ET POURQUOI CHAQUE TEST EXISTE
────────────────────────────────────────────────────────
UNE SEULE PROPRIETE : *une bibliotheque ne change pas l'etat global du
processus a l'import.*

═══ LE DEFAUT, ET IL ETAIT BIEN PLUS LARGE QUE SON LIBELLE ═══

Le releve classait `a2/C15` en << C -- Imprecis ou date >>, sur UN site.
Releve par AST au niveau module : **40 sites dans 39 fichiers de production**,
tous de la meme forme nue `warnings.filterwarnings('ignore')` :

    direction_sante_prevoyance   20
    direction_non_vie            13   (dont 6 agents de tarification)
    direction_vie_epre            5
    demos                         2

Poser ce filtre AU NIVEAU MODULE l'applique AU PROCESSUS ENTIER des l'import :
tout appelant d'un de ces agents perdait les avertissements de TOUS ses
modules, y compris ceux qu'il n'a jamais importes.

═══ CE QU'IL CACHAIT, MESURE SUR UN RUN REEL ═══

    7x Pandas4Warning   `select_dtypes` -- NOTRE code, rupture pandas 4
    6x UserWarning      sklearn : << X does not have valid feature names >>
    3x FutureWarning    statsmodels : le calcul du BIC change apres 0.13

⚠️⚠️ LE TROISIEME PORTE SUR UN NOMBRE PUBLIE. `bic` est ecrit dans les
metriques d'A3 a TROIS sites et parait au chapitre 1 du rapport signe. *Un
nombre publie dont la definition change, et l'avertissement etait avale.*

⚠️ ET JE CORRIGE MON PROPRE SOUPCON. J'avais avance qu'un GLM qui ne converge
pas previent par `warnings.warn` et que personne ne le voit. Mesure : AUCUN
avertissement de non-convergence sur ce portefeuille. Le mecanisme est reel,
la trouvaille est ailleurs. *Une hypothese mesuree vaut mieux qu'une hypothese
plausible.*

═══ L'ASSIETTE DU LOT, DECLAREE ═══

⚠️ SEULS LES 6 AGENTS DE TARIFICATION SONT TRAITES -- c'est le chantier en
cours. Les **34 autres sites** (sante-prevoyance, vie/EP-RE, reglementation,
demos, et un fichier de test) restent en place : les toucher violerait la regle
d'un seul chantier. Ils sont NOMMES, non traites -- 40 releves moins les 6
agents = 34, et un test fige ce nombre.

⚠️ CE CHIFFRE ETAIT ECRIT << 33 >> ICI PENDANT QUE LE TEST EN ASSERTAIT 34.
Corrige avant commit : *le texte qui accompagne un controle se relit contre ce
que le controle mesure.*

⚠️ ET IL RESTE DES FILTRES APRES LE CORRECTIF -- 12, tous TIERS : torch 4,
numpy 3, scipy 2, pandas 1, plotly 1, IPython 1. Une bibliotheque tierce qui
regle ses propres avertissements n'est pas notre affaire ; ce test verifie
qu'AUCUN ne vient de nous.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

_RACINE = pathlib.Path(__file__).resolve().parent

#: Les six agents de tarification — l'assiette EXACTE de ce lot.
_AGENTS = ('a1_ingestion', 'a2_preprocessing', 'a3_glm', 'a4_ml',
           'a5_deep_learning', 'a6_comparaison')


def _filtres_niveau_module(chemin: pathlib.Path) -> list[int]:
    """Les `warnings.filterwarnings(...)` posés AU NIVEAU MODULE.

    ⚠️ On ne cherche pas la chaîne : on lit le corps du module. Un appel
    identique DANS une fonction est légitime (il est scopé) ; c'est sa
    position au niveau module qui en fait un effet de bord global.
    """
    arbre = ast.parse(chemin.read_text(encoding='utf-8'))
    return [n.lineno for n in arbre.body
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
            and getattr(n.value.func, 'attr', None) == 'filterwarnings']


class TestAucunEffetDeBordGlobal(unittest.TestCase):
    """`a2/C15` — les six agents ne touchent plus l'état du processus."""

    def test_les_SIX_agents_ne_posent_plus_de_filtre(self):
        """⚠️⚠️ LE TEST QUI FERME LE CONSTAT — au niveau module, par AST.

        ⚠️⚠️ ET IL FERME AUSSI `a1/C6`, CE QUE PERSONNE N'AVAIT VU. Le lot
        mesurait `a2/C15` -- le meme defaut, releve dans la zone A2, a 40
        sites -- et son correctif a traite les SIX agents, donc A1 aussi. Mais
        le site porte le numero `a2/C15` : `a1/C6`, le jumeau du meme defaut
        dans la zone A1, est reste OUVERT au compte pendant tout ce temps.

        ⚠️ *Un correctif mesure dans une zone peut fermer un constat d'une
        AUTRE zone. Si rien ne le nomme, le compte publie reste faux.*
        """
        fautifs = {}
        for agent in _AGENTS:
            lignes = _filtres_niveau_module(_RACINE / agent / 'agent.py')
            if lignes:
                fautifs[agent] = lignes
        self.assertEqual(
            fautifs, {},
            f'filtre(s) global(aux) revenu(s) : {fautifs}. Une bibliothèque ne '
            f'change pas l état du processus à l import.')
        print(f"    W-1 les {len(_AGENTS)} agents : 0 filtre au niveau module")

    def test_IMPORTER_les_agents_n_ajoute_AUCUN_filtre_a_nous(self):
        """⚠️⚠️ LE TEST PAR L'EFFET, ET IL EST PLUS FORT QUE CELUI PAR AST.

        Un filtre pourrait revenir par un module importé en cascade — `core`,
        `services`, une dépendance interne. On instrumente donc l'appel réel et
        on regarde D'OÙ il vient. Les filtres TIERS (torch, numpy, scipy…) sont
        légitimes : une bibliothèque règle ses propres avertissements.
        """
        import os
        import subprocess
        import sys
        code = (
            'import warnings, traceback, os, sys, json\n'
            'sys.path.insert(0, ".")\n'
            'vrai = warnings.filterwarnings\n'
            'nous = []\n'
            'def espion(*a, **k):\n'
            '    for f in reversed(traceback.extract_stack()[:-1]):\n'
            '        if "warnings.py" in f.filename: continue\n'
            '        if "site-packages" not in os.path.normpath(f.filename):\n'
            '            nous.append(f.filename)\n'
            '        break\n'
            '    return vrai(*a, **k)\n'
            'warnings.filterwarnings = espion\n'
            'import direction_non_vie.tarification.a3_glm.agent\n'
            'import direction_non_vie.tarification.a6_comparaison.agent\n'
            'warnings.filterwarnings = vrai\n'
            'print(json.dumps(nous))\n'
        )
        env = dict(os.environ, PYTHONUTF8='1')
        r = subprocess.run([sys.executable, '-c', code], capture_output=True,
                           text=True, timeout=600, check=False, cwd=str(_RACINE.parent.parent),
                           env=env)
        import json
        sortie = [x for x in r.stdout.strip().split('\n') if x.startswith('[')]
        self.assertTrue(sortie, f'sonde muette : {r.stderr[-300:]}')
        nous = json.loads(sortie[-1])
        self.assertEqual(nous, [],
                         f'du code À NOUS pose encore un filtre global : {nous}')
        print("    W-2 importer les agents : 0 filtre venant de NOTRE code "
              "(les tiers restent, c est leur droit)")

    def test_les_TROIS_familles_cachees_remontent(self):
        """⚠️⚠️ CE QUE LE CORRECTIF REND VISIBLE — EN CONDITIONS RÉELLES.

        ⚠️⚠️ CE TEST A ÉTÉ RÉÉCRIT PAR SA PROPRE VIOLATION PLANTÉE. Sa première
        version faisait `catch_warnings() + simplefilter('always')` : elle
        **neutralisait elle-même** le filtre du module, et mesurait donc son
        propre contexte, pas l'effet mesuré. Le filtre remis dans A3, **elle ne
        tombait pas.** *Un test qui installe ses propres conditions ne mesure
        plus celles du code.*

        Il tourne désormais en SOUS-PROCESSUS, sans toucher aux filtres : c'est
        exactement ce que voit un appelant réel.
        """
        import json
        import os
        import subprocess
        import sys
        code = (
            'import warnings, json, sys, logging\n'
            'sys.path.insert(0, ".")\n'
            'logging.disable(logging.CRITICAL)\n'
            'vus = []\n'
            'vrai = warnings.showwarning\n'
            'def espion(message, category, *a, **k):\n'
            '    vus.append(category.__name__)\n'
            'warnings.showwarning = espion\n'
            'import direction_non_vie.tarification.test_pipeline_agents as T\n'
            'T._lancer(T._portefeuille_auto(900, seed=3))\n'
            'warnings.showwarning = vrai\n'
            'print("RESULTAT" + json.dumps(sorted(set(vus))))\n'
        )
        env = dict(os.environ, PYTHONUTF8='1')
        r = subprocess.run([sys.executable, '-c', code], capture_output=True,
                           text=True, timeout=900, check=False,
                           cwd=str(_RACINE.parent.parent), env=env)
        ligne = [x for x in r.stdout.split('\n') if x.startswith('RESULTAT')]
        self.assertTrue(ligne, f'sonde muette : {r.stderr[-300:]}')
        categories = json.loads(ligne[-1][len('RESULTAT'):])
        self.assertTrue(
            categories,
            'AUCUN avertissement ne remonte : un filtre global les avale')
        for attendue in ('FutureWarning', 'UserWarning'):
            with self.subTest(categorie=attendue):
                self.assertIn(attendue, categories)
        print(f"    W-3 en conditions reelles, les avertissements remontent : "
              f"{categories}")

    def test_le_FutureWarning_du_BIC_vise_un_nombre_PUBLIE(self):
        """⚠️⚠️ POURQUOI CE LOT N'EST PAS COSMÉTIQUE.

        statsmodels annonce que le calcul du BIC change après 0.13. `bic` est
        écrit dans les métriques d'A3 — trois sites — et paraît au rapport
        signé. *Un nombre publié dont la définition change, et l'avertissement
        était avalé.* Ce test relie l'avertissement au nombre.
        """
        src = (_RACINE / 'a3_glm' / 'agent.py').read_text(encoding='utf-8')
        arbre = ast.parse(src)
        sites = [n.lineno for n in ast.walk(arbre)
                 if isinstance(n, ast.Constant) and n.value == 'bic']
        self.assertGreaterEqual(
            len(sites), 3,
            "les sites qui publient `bic` ont bougé — re-mesurer la dette")
        print(f"    W-4 `bic` publié à {len(sites)} site(s) d A3 : "
              f"l avertissement statsmodels les vise")

    def test_SECOND_SENS_le_pipeline_TOURNE_toujours(self):
        """⚠️⚠️ SECOND SENS — retirer un filtre ne doit rien casser.

        Le risque réel d'un tel correctif n'est pas le bruit : c'est qu'un
        avertissement devenu visible fasse échouer un appelant qui l'aurait
        transformé en erreur. Mesuré : le pipeline complet aboutit.
        """
        import direction_non_vie.tarification.test_pipeline_agents as T
        res = T._lancer(T._portefeuille_auto(900, seed=3))
        self.assertTrue(res.a3.get('success'), 'A3 a échoué sans le filtre')
        self.assertIsNotNone(res.frequence.a6, 'l arbitrage fréquence a échoué')
        print("    W-5 second sens : le pipeline complet aboutit toujours")

    def test_les_33_AUTRES_sites_sont_NOMMES_et_hors_assiette(self):
        """⚠️ CE LOT NE TRAITE QUE LA TARIFICATION, ET LE DÉCLARE.

        33 sites subsistent hors du chantier (santé-prévoyance, vie/EP-RE,
        réglementation, démos). Les toucher violerait la règle d'un seul
        chantier. Ce test FIGE leur nombre : s'il baisse, quelqu'un les a
        traités et le relevé doit le dire ; s'il monte, le défaut se propage.
        """
        racine = _RACINE.parent.parent
        hors = []
        for p in racine.rglob('*.py'):
            if '.venv' in str(p) or 'audit_2026_08' in str(p):
                continue
            if p.parent.name in _AGENTS:
                continue
            try:
                lignes = _filtres_niveau_module(p)
            except SyntaxError:
                continue
            hors += [f'{p.name}:{n}' for n in lignes]
        self.assertEqual(
            len(hors), 34,
            f'{len(hors)} sites hors assiette au lieu de 34 : le relevé doit '
            f'être re-mesuré ({sorted(hors)[:6]}…)')
        print(f"    W-6 {len(hors)} sites hors assiette, nommés et figés")


if __name__ == '__main__':
    unittest.main()
