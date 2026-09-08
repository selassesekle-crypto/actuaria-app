# -*- coding: utf-8 -*-
"""UN SOCLE QUI A BESOIN D'UNE DIRECTION N'EST PAS UN SOCLE.

Releve par AST le 05/09/2026 : **un seul** import de PRODUCTION remontait de
`core/` vers une direction --

    core/elasticite.py:969
        from direction_non_vie.tarification.pipeline_tarifaire
            import CHARGEMENTS_DEFAUT

Il etait LOCAL, donc invisible a l'import du module ; il se payait a
l'EXECUTION. Mesure du 05/09/2026 :

    core.elasticite importe seul            : 0,05 s, 0 module direction_*
    ce que coutait l'import de la l. 969    : 4,41 s, 14 modules amenes,
        dont direction_non_vie.provisionnement
             direction_non_vie.reglementation
             tarification.services.tarif_excel
    ...pour obtenir QUATRE FLOTTANTS qui existaient deja dans le socle, sous
    `core.plan_tarifaire.Chargements`, aux memes valeurs (verifie).

Ce que cette sentinelle exige :
  SEP-1  AUCUN module de production de `core/` n'importe une direction ;
  SEP-2  la liste des TESTS derogataires est FERMEE -- ni plus, ni moins ;
  SEP-3  le repli de chargements de la direction EST celui du socle
         (identite, pas egalite : deux copies pourraient rediverger) ;
  SEP-4  il DERIVE de `Chargements`, il ne recopie pas quatre litteraux ;
  SEP-5  **et cela se mesure PAR EXECUTION** : dans un sous-processus neuf,
         `sensibilite_tarifaire` produit ses chargements sans qu'AUCUN
         module `direction_*` ne soit charge.

⚠️⚠️ SEP-5 EXISTE PARCE QUE SEP-1 LIT DU TEXTE. Un import peut naitre d'un
`importlib.import_module(nom)` construit a l'execution, qu'aucun releve AST ne
voit. *Un controle qui lit le code et non le comportement passe.*

⚠️ CE LOT NE CHANGE AUCUNE VALEUR. `taxes = 0.33` reste le taux AUTO applique
aux 20 LoB (MRH 30 %, RC 9 %) : c'est un constat OUVERT, qui demande une
SOURCE externe (le CGI). Le lot deplace l'ORIGINE de la valeur, jamais la
valeur.

Tout en `unittest.TestCase` : la gate lance `unittest discover`.
"""
import ast
import dataclasses
import os
import pathlib
import subprocess
import sys
import textwrap
import unittest

_ICI = pathlib.Path(os.path.abspath(__file__)).parent
_RACINE = _ICI.parent
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

#: Les paquets de direction. ⚠️ Trois, pas un : un controle qui ne surveille
#: que `direction_non_vie` laisserait passer un import vers la Vie.
_DIRECTIONS = ('direction_non_vie', 'direction_vie', 'direction_sante')

#: LES TESTS DEROGATAIRES, NOMMES ET FERMES. Un test de `core/` a le droit de
#: verifier qu'une direction consomme correctement le socle -- c'est meme
#: souvent le seul endroit ou ce contrat s'observe. Mais la liste est FIGEE :
#: elle ne peut ni grossir en silence, ni retrecir sans qu'on le sache.
#: ⚠️ La cle est le NOM DE FICHIER, la valeur le MOTIF -- sans motif, une
#: derogation devient une habitude.
_TESTS_DEROGATAIRES: dict[str, str] = {
    'test_apercu_caviarde.py':
        "verifie que le caviardage RGPD tient sur le mapping LLM d'une "
        "direction : le contrat ne s'observe que du cote consommateur.",
    'test_elasticite.py':
        "verifie que l'elasticite calculee par le socle atteint A4 -- un "
        "calcul qui n'atteint aucun livrable n'existe pas.",
    'test_format_fr.py':
        "verifie que le formatage francais du socle est celui qu'emploie le "
        "rapport A7 signe.",
    'test_narration.py':
        "verifie que la narration du socle atteint le rapport modeles de la "
        "tarification, prompt compris.",
    # ⚠️⚠️ CE FICHIER-CI. Il n'est pas au-dessus de sa propre regle : SEP-2 l'a
    # attrape a sa premiere execution, et c'est la preuve que la liste mord.
    'test_separabilite_socle.py':
        "SEP-3 compare les DEUX cotes du repli de chargements : prouver que "
        "l'objet est le meme exige de le lire chez le consommateur autant "
        "que chez le producteur.",
}


def _imports_de_direction(chemin: pathlib.Path) -> list[tuple[int, str]]:
    """Les imports de direction d'un fichier, RELEVES PAR AST.

    ⚠️ Par AST et non par `grep` : un `grep` ne voit ni les imports en
    plusieurs lignes, ni la difference entre un import et une mention en
    commentaire ou en docstring -- et ce fichier-ci en contient beaucoup.
    """
    arbre = ast.parse(chemin.read_text(encoding='utf-8'), filename=str(chemin))
    trouves = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            modules = [alias.name for alias in noeud.names]
        elif isinstance(noeud, ast.ImportFrom):
            # ⚠️ Un import RELATIF (`level > 0`) ne peut pas sortir de `core`
            # sans remonter au-dessus de la racine : il n'est pas concerne.
            modules = [noeud.module] if noeud.module and not noeud.level else []
        else:
            continue
        for module in modules:
            if module.split('.')[0] in _DIRECTIONS:
                trouves.append((noeud.lineno, module))
    return trouves


class TestLeSocleNeRemonteJamais(unittest.TestCase):

    def _fichiers_de_core(self):
        return sorted(p for p in (_RACINE / 'core').rglob('*.py'))

    def test_SEP1_aucun_module_de_production_de_core_n_importe_une_direction(self):
        """⚠️⚠️ LE COEUR DU LOT."""
        fautifs = []
        for chemin in self._fichiers_de_core():
            if chemin.name.startswith('test_'):
                continue
            for lineno, module in _imports_de_direction(chemin):
                fautifs.append(f'{chemin.relative_to(_RACINE).as_posix()}:'
                               f'{lineno} -> {module}')
        self.assertEqual(
            fautifs, [],
            "le socle remonte vers une direction : " + ' ; '.join(fautifs) +
            ". Un socle qui a besoin d'une direction ne partirait pas seul le "
            "jour de la licence. Si la valeur cherchee existe deja dans "
            "`core`, lisez-la la ; sinon, c'est une decision de conception.")

    def test_SEP2_la_liste_des_tests_derogataires_est_FERMEE(self):
        """⚠️ DANS LES DEUX SENS. Une derogation de plus doit rougir ; une
        derogation qui n'a plus lieu d'etre doit sortir de la liste."""
        constate = {}
        for chemin in self._fichiers_de_core():
            if not chemin.name.startswith('test_'):
                continue
            liens = _imports_de_direction(chemin)
            if liens:
                constate[chemin.name] = liens
        self.assertEqual(
            sorted(constate), sorted(_TESTS_DEROGATAIRES),
            f"la liste des tests derogataires ne decrit plus le depot. "
            f"Constate : {sorted(constate)}. Declare : "
            f"{sorted(_TESTS_DEROGATAIRES)}. Ajoutez le fichier AVEC SON "
            f"MOTIF, ou retirez-le s'il ne remonte plus.")

    def test_SEP2b_chaque_derogation_porte_un_MOTIF(self):
        for nom, motif in _TESTS_DEROGATAIRES.items():
            with self.subTest(fichier=nom):
                self.assertGreater(
                    len(motif.strip()), 60,
                    f'{nom} deroge sans dire pourquoi')


class TestLeRepliDeChargements(unittest.TestCase):

    def test_SEP3_la_direction_ne_lit_PLUS_le_repli_du_tout(self):
        """⚠️⚠️ CE CONTROLE A CHANGE DE SUJET LE 08/09/2026, ET IL EST DEVENU
        PLUS FORT.

        Il prouvait que la direction et le socle partageaient LE MEME objet
        (`is`, pas `==`) -- un garde contre le defaut d'origine, ou la
        direction s'etait redonne sa propre copie des quatre litteraux.

        L'arbitrage a supprime le repli lui-meme : un plan qui ne declare pas
        ses chargements n'obtient plus un prix approximatif, il n'obtient PAS
        DE PRIME COMMERCIALE. La direction n'importe donc plus rien du tout,
        et *ne rien partager est plus sur que partager le meme objet.*
        """
        from direction_non_vie.tarification import pipeline_tarifaire
        self.assertFalse(
            hasattr(pipeline_tarifaire, 'CHARGEMENTS_DEFAUT'),
            "la direction a repris un repli de chargements. Depuis "
            "l'arbitrage du 08/09/2026, aucun chemin de prix n'en lit un : "
            "frais, commission et marge se declarent au plan, ou la prime "
            "commerciale n'existe pas.")

    def test_SEP4_le_repli_a_CESSE_de_deriver_et_la_raison_a_disparu(self):
        """⚠️⚠️ LA DERIVATION EXISTAIT POUR EMPECHER DEUX LISTES DE DIVERGER.
        `Chargements` n'a plus de valeurs par defaut -- une valeur par defaut
        EST une valeur devinee --, il n'y a donc plus rien a deriver, et plus
        rien qui puisse diverger : *il ne reste qu'une seule liste.*

        Ce qui subsiste sous ce nom est une CONVENTION DE STRUCTURE, pour la
        marge technique de `core/elasticite.py` : `prime x (1 - commission) -
        charge x (1 + frais)`. Rien n'y est normatif, et ce module porte deja
        le vocabulaire de source qui le dit.
        """
        from core.plan_tarifaire import CHARGEMENTS_DEFAUT, Chargements
        self.assertEqual(sorted(CHARGEMENTS_DEFAUT),
                         ['commission', 'frais', 'marge', 'taxes'])
        nu = dataclasses.asdict(Chargements())
        for champ in ('frais', 'commission', 'marge', 'taxes'):
            self.assertIsNone(
                nu[champ],
                f"`Chargements.{champ}` a repris une valeur par defaut : le "
                f"systeme redeviendrait capable de deviner une decision "
                f"commerciale a la place du client.")

    def test_SEP4b_le_repli_est_DECLARE_pour_ce_qu_il_est_devenu(self):
        """⚠️⚠️ CE QUI RESTE OUVERT DOIT LE RESTER VISIBLEMENT -- et ce qui a
        change de nature doit le dire. Ce controle exigeait le mot << REPLI >>
        dans la docstring de `Chargements`. Le repli a disparu ; exiger encore
        ce mot ferait survivre une affirmation fausse dans un texte signe.

        Ce qui doit s'y lire desormais : que la prime commerciale est une
        DECISION, et que le systeme ne la devine pas.
        """
        from core import plan_tarifaire
        doc = (plan_tarifaire.Chargements.__doc__ or '').upper()
        # ⚠️ On vise la DOCTRINE, pas un mot : << DECISION >> s'ecrit avec un
        # accent dans le texte, et une assertion sur la forme non accentuee
        # echouait. C'est le piege des regex qui cherchent une graphie que le
        # texte n'emploie pas -- deja paye sept fois dans ce chantier.
        self.assertIn('NE LES DEVINE PAS', doc,
                      "la docstring ne dit plus que le systeme ne devine pas "
                      "les chargements a la place du client")
        self.assertNotIn(
            'LE REPLI D', doc,
            "la docstring parle encore d'un repli applique : il n'y en a plus")


class TestParExecutionEtPasParLeTexte(unittest.TestCase):
    """⚠️⚠️ SEP-1 LIT DU TEXTE. Celui-ci REGARDE CE QUI SE CHARGE."""

    def test_SEP5_sensibilite_tarifaire_s_execute_sans_aucune_direction(self):
        code = textwrap.dedent('''
            import sys
            import core.elasticite as E
            r = E.sensibilite_tarifaire(None, None, {'etat': 'NON_ESTIMEE'})
            charges = sorted(m for m in sys.modules
                             if m.startswith('direction_'))
            print(repr(charges))
            print(repr(r['conventions']['chargements']))
        ''')
        # ⚠️ SOUS-PROCESSUS OBLIGATOIRE : dans le processus de la gate, une
        # direction est deja chargee par d'autres tests. Mesurer ici serait
        # mesurer autre chose.
        proc = subprocess.run(
            [sys.executable, '-B', '-c', code],
            cwd=str(_RACINE), capture_output=True, text=True,
            encoding='utf-8', errors='replace', check=False,
            env=dict(os.environ, PYTHONUTF8='1',
                     PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(proc.returncode, 0,
                         f'le sous-processus a echoue :\n{proc.stderr[-2000:]}')
        lignes = [l for l in proc.stdout.splitlines() if l.strip()]
        charges = ast.literal_eval(lignes[0])
        self.assertEqual(
            charges, [],
            f"executer `sensibilite_tarifaire` charge encore une direction : "
            f"{charges}. Un import construit a l'execution echappe a SEP-1 ; "
            f"celui-ci le voit.")
        # ...et elle produit bien ses chargements, sinon le test ci-dessus
        # serait vert pour la mauvaise raison : une fonction qui echoue tot
        # ne charge rien non plus.
        chargements = ast.literal_eval(lignes[1])
        self.assertEqual(sorted(chargements),
                         ['commission', 'frais', 'marge', 'taxes'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
