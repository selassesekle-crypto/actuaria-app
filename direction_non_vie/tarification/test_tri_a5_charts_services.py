"""Controles positifs — TRI des trois dernieres zones : `a5`, `charts`, `services`.

CE QUE CE LOT FERME, ET CE QU'IL LAISSE OUVERT EN LE DISANT
────────────────────────────────────────────────────────────

Le TRI etait la derniere passe de l'audit : **11 zones sur 14 tracees, 9
constats jamais alles au site**. Ils y sont alles. Sept sont fermes ici, deux
restent ouverts avec leur raison, **et un constat NEUF a ete ouvert par la
trace elle-meme**.

═══ ⚠️⚠️ LE CONSTAT NEUF, ET C'EST LE PLUS SERIEUX ═══

En tracant `a5/C8` (la liste noire de A5 porte du vocabulaire Vie/Sante), la
vraie question est apparue : **que devient un facteur DECLARE AU PLAN dont le
nom figure dans cette liste noire ?**

A5 construit ses features en prenant *tout le dataframe SAUF* la liste noire,
puis croise avec la liste blanche du plan (`construire_matrice_x`). Violation
plantee le 31/08 -- on retire UNE colonne declaree avant l'appel :

```
  temoin  (23 colonnes) -> 23 retenues | exclusions 0 | alertes 0
  amputee (22 colonnes) -> 22 retenues | exclusions 0 | alertes 0   <-- RIEN
```

**Un facteur du plan SIGNE peut disparaitre sans un mot.** *La liste blanche
surveille l'INTERSECTION, jamais l'ABSENCE : ce qui a ete mange en amont lui
est invisible.* C'est `plan/C3` -- « un `type` mal orthographie detruit un
facteur en silence » -- ferme au niveau du plan et **rouvert un etage plus
bas**.

⚠️ **AMPLEUR MESUREE, NON GONFLEE : 0 victime sur les 20 plans.** Aucun plan ne
nomme une colonne de la liste noire, et `COLS_CONTAMINEES` ne porte que des
noms composes (`log_cout`, `prime_pure_obs`...), pas des mots generiques -- la
sous-chaine y est donc bien moins dangereuse que dans `conformite/C3`. Le
defaut est **structurel et latent**, pas actif.

⚠️⚠️ `TRI-7` MONTE LA GARDE EN ATTENDANT LE CORRECTIF : il verifie qu'aucun des
20 plans ne declare une colonne que la liste noire mangerait. *Il ne repare
rien -- il empeche le defaut latent de devenir actif sans qu'on le sache.*

═══ CE QUI RESTE OUVERT, ET POURQUOI ═══

⛔ **`charts/C8`** -- `CONFIG_PLOTLY` reecrite en dur dans `actuaria_app.py`.
**L'app Streamlit est hors perimetre par arbitrage de Selasse du 25/08** : elle
disparait, on n'y touche pas, meme pour une phrase.
⚠️ **ET LE CONSTAT EST REFUTE SUR UN POINT** : il disait « Meme valeur
aujourd'hui ». Mesure du 31/08 -- **deux** sites (l.4188 et l.4248), et la
valeur **DIFFERE** : `CONFIG_PLOTLY` porte `responsive: True`, le litteral de
l'app ne l'a pas. *Ce n'est plus « deux endroits a changer demain », c'est deux
comportements DIFFERENTS aujourd'hui.*

⛔ **`services/C7`** -- `raisons_plafond` atteint 2 surfaces sur 6. Le porter
aux quatre autres (Excel A6 + les trois formats du rapport equipe) ajoute une
phrase a **quatre livrables signes** : c'est un lot de PUBLICATION a lui seul,
de la meme famille que l'etape 4 d'`unite_exposition`, et il doit porter ses
propres controles. *Ne pas l'empiler dans une passe de tri.*
"""

from __future__ import annotations

import ast
import glob
import inspect
import pathlib
import re
import unittest

from core.charts_tarif import CONFIG_PLOTLY, GLYPHE_RAG_EXCEL, _qnorm
from core.plan_tarifaire import PlanTarifaire
from direction_non_vie.tarification.a5_deep_learning.agent import (
    COLS_A_EXCLURE,
    COLS_CONTAMINEES,
)
from direction_non_vie.tarification.services.excel_helpers import _kpi

_RACINE = pathlib.Path(__file__).resolve().parents[2]


def _src(chemin: str) -> str:
    return (_RACINE / chemin).read_text(encoding='utf-8')


def _ligne_qui_affirme(texte: str, debut: str) -> str:
    """LA ligne qui porte l'affirmation, reperee par son debut.

    ⚠️⚠️ MES QUATRE PREMIERS CONTROLES SONT TOMBES SUR MON PROPRE CORRECTIF.
    Ils interdisaient une chaine PARTOUT dans un en-tete ; or un correctif
    honnete **CITE** la phrase fautive pour dire ce qu'il repare. *Une citation
    n'est pas une affirmation* -- exactement la distinction que porte
    `_HORS_ASSIETTE` entre NOMMER un constat et le FERMER.

    ⚠️ Ma premiere correction listait des prefixes a exclure : du bricolage de
    chaines, aussi fragile que le defaut. *On ne retire pas les citations -- on
    designe la ligne qui AFFIRME.*
    """
    for ligne in texte.split('\n'):
        if ligne.strip().startswith(debut):
            return ligne
    raise AssertionError(f'aucune ligne ne commence par {debut!r} : le '
                         f'controle ne surveille plus rien')


class TestZoneA5(unittest.TestCase):

    def test_a5_C3_les_courbes_lisent_les_pertes_REELLES(self):
        """⚠️⚠️ `a5/C3` ETAIT AU QUATRIEME ETAT : corrige ET epingle par
        `test_les_courbes_d_apprentissage_portent_les_pertes_REELLES`, mais
        **jamais NOMME** -- donc invisible a `ARCH-1`, donc compte OUVERT.

        L'historique empile `{'epoch','train','val'}` ; le code lisait
        `loss_train` / `loss_val` / `gini_val`. Les trois traces sortaient a
        ZERO, et la « Best epoque » -- index du maximum de ces zeros -- valait
        toujours 1. `gini_val` n'a **jamais** ete enregistre.
        """
        source = _src('direction_non_vie/tarification/a5_deep_learning/'
                      'agent.py')
        fonction = next(
            n for n in ast.walk(ast.parse(source))
            if isinstance(n, ast.FunctionDef)
            and n.name == '_generer_graphiques')
        # ⚠️ SEULEMENT `h.get(...)` — la lecture de l'HISTORIQUE. Ma
        # premiere version comptait tous les `.get` de la methode (layout,
        # metriques, options) et rendait neuf cles. *Une sonde qui elargit son
        # assiette mesure autre chose que ce qu'elle annonce.*
        cles = sorted({a.args[0].value for a in ast.walk(fonction)
                       if isinstance(a, ast.Call)
                       and isinstance(a.func, ast.Attribute)
                       and a.func.attr == 'get' and a.args
                       and isinstance(a.func.value, ast.Name)
                       and a.func.value.id == 'h'
                       and isinstance(a.args[0], ast.Constant)})
        self.assertEqual(
            cles, ['train', 'val'],
            f"les figures lisent {cles} : l'historique porte 'train'/'val'")
        traces = [kw.value.value for n in ast.walk(fonction)
                  if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute)
                  and n.func.attr == 'add_trace'
                  for kw in ast.walk(n)
                  if isinstance(kw, ast.keyword) and kw.arg == 'name'
                  and isinstance(kw.value, ast.Constant)]
        self.assertNotIn('Gini Val', traces,
                         'un Gini par epoque n a jamais ete enregistre : la '
                         'trace ne peut etre qu une ligne de zeros')
        self.assertEqual(len(traces), 4,
                         f'CANN et TabNet, deux pertes chacun : {traces}')
        print(f"    TRI-1 a5/C3 : les 2 figures lisent {cles}, {len(traces)} "
              f"traces, aucune « Gini Val »")

    def test_a5_C9_l_en_tete_ne_porte_plus_de_compte_ecrit_a_la_main(self):
        """⚠️ Il annonçait « 7 tests » : 3 au releve, **12** aujourd'hui.
        *On ne remplace pas un compte a la main par un autre compte a la
        main* -- `unittest` le publie a chaque execution."""
        chemin = ('direction_non_vie/tarification/a5_deep_learning/'
                  'test_a5_deep_learning.py')
        source = _src(chemin)
        # ⚠️ LA LIGNE DE TITRE, pas tout l'en-tete : le correctif y CITE
        # « 7 tests » pour dire ce qu'il repare, et ma premiere version
        # comptait cette citation comme une affirmation.
        titre = source.split('"""')[1].strip().splitlines()[0]
        chiffres = re.findall(r'(\d+)\s+tests', titre)
        self.assertEqual(chiffres, [],
                         f"la ligne de titre annonce encore un nombre de "
                         f"tests : {chiffres}. Ligne : {titre!r}")
        reels = [n.name for n in ast.walk(ast.parse(source))
                 if isinstance(n, ast.FunctionDef)
                 and n.name.startswith('test_')]
        print(f"    TRI-2 a5/C9 : aucun compte dans l'en-tete "
              f"({len(reels)} tests reels, publies par unittest)")

    def test_a5_C8_la_liste_noire_ne_mange_aucune_colonne_DECLAREE(self):
        """⚠️⚠️ `TRI-7` — LE TEMOIN QUI GARDE LE CONSTAT NEUF. Les entrees
        Vie/Sante restent : les RETIRER **ajouterait** une variable si un
        fichier client en portait une, donc deplacerait un prix. Elles sont
        inoffensives tant qu'aucun plan ne nomme l'une d'elles.

        *Ce controle ne repare pas le defaut structurel -- il empeche qu'il
        devienne actif en silence.*
        """
        noir = set(COLS_A_EXCLURE)
        victimes = []
        for fichier in sorted(glob.glob('plans/*.yaml')):
            plan = PlanTarifaire.depuis_yaml(fichier)
            for col in plan.colonnes_produites():
                if col in noir or any(m in col for m in COLS_CONTAMINEES):
                    victimes.append((pathlib.Path(fichier).name, col))
        self.assertEqual(
            victimes, [],
            f"{len(victimes)} colonne(s) DECLAREE(S) au plan seraient "
            f"supprimee(s) EN SILENCE par A5 : {victimes}. Le defaut latent "
            f"vient de devenir ACTIF -- voir l'en-tete de ce fichier.")
        print(f"    TRI-7 a5/C8 : 0 / {len(glob.glob('plans/*.yaml'))} plans "
              f"ne nomment une colonne que la liste noire mangerait")


class TestZoneCharts(unittest.TestCase):

    def test_charts_C6_la_docstring_dit_QUELLE_erreur(self):
        """⚠️ L'algorithme etait juste ; c'est le mot manquant qui rendait le
        chiffre faux. Acklam publie une erreur RELATIVE de 1,15e-9, atteinte
        (1,129e-9) ; l'erreur ABSOLUE monte a 5,62e-9, soit x 4,7 l'annonce."""
        doc = inspect.getdoc(_qnorm) or ''
        resume = doc.strip().splitlines()[0]
        self.assertIn('RELATIVE', doc.upper(),
                      'la docstring ne dit toujours pas DE QUELLE erreur')
        self.assertNotIn('|err|', resume,
                         f"la ligne de resume porte encore l'annonce "
                         f"ambigue : {resume!r}")
        # ⚠️ Second sens SANS scipy : l'inverse compose avec la CDF redonne x.
        import math
        for x in (-3.5, -1.0, -0.2, 0.0, 0.2, 1.0, 3.5):
            p = 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
            self.assertAlmostEqual(float(_qnorm(p)), x, places=6)
        print("    TRI-3 charts/C6 : la docstring nomme l'erreur RELATIVE, "
              "et l'inverse recompose x a 1e-6")

    def test_charts_C7_l_en_tete_ne_declare_plus_kaleido_absent(self):
        """⚠️ Mesure : kaleido 1.3.0 installe, `to_image(png)` rend 20 826
        octets. *Le suivi etait clos, la note ne l'etait pas.*"""
        ligne = _ligne_qui_affirme(
            _src('core/charts_tarif.py').split('"""')[1], '• Excel / Word')
        self.assertNotIn('kaleido absent', ligne,
                         f'la ligne qui affirme le dit encore : {ligne!r}')
        self.assertIn('DISPONIBLE', ligne)
        import importlib.metadata as meta
        try:
            version = meta.version('kaleido')
        except meta.PackageNotFoundError:     # pragma: no cover
            version = None
        self.assertIsNotNone(
            version, "kaleido n'est plus installe : l'en-tete corrigee "
                     "redeviendrait fausse dans l'autre sens")
        print(f"    TRI-4 charts/C7 : en-tete corrigee, kaleido {version} "
              f"present")


class TestZoneServices(unittest.TestCase):

    def test_services_C8_le_compte_d_onglets_ANNONCE_est_celui_PRODUIT(self):
        """⚠️⚠️ ON DERIVE LES DEUX COTES. Annoncer « 6 » en dur reproduirait
        le defaut au lot suivant : on compte les `create_sheet` du code."""
        source = _src('direction_non_vie/tarification/services/'
                      'tarif_excel.py')
        fonction = next(n for n in ast.walk(ast.parse(source))
                        if isinstance(n, ast.FunctionDef)
                        and n.name == 'export_excel_a3')
        feuilles = [c for c in ast.walk(fonction)
                    if isinstance(c, ast.Call)
                    and isinstance(c.func, ast.Attribute)
                    and c.func.attr == 'create_sheet']
        produits = len(feuilles) + 1          # + la feuille active initiale
        annonce = re.search(r'\((\d+) onglets\)',
                            ast.get_docstring(fonction) or '')
        self.assertIsNotNone(annonce, "la docstring n'annonce plus de compte")
        self.assertEqual(
            int(annonce.group(1)), produits,
            f"la docstring annonce {annonce.group(1)} onglets, le code en "
            f"produit {produits}")
        print(f"    TRI-5 services/C8 : annonce et code concordent "
              f"({produits} onglets)")

    def test_services_C9_le_mot_le_plus_FORT_est_le_plus_alarmant(self):
        """⚠️⚠️ Le triptyque publiait « ✗ Attention » pour ROUGE contre
        « △ À surveiller » pour AMBRE : *l'escalade s'inversait sur le seul
        mot que l'actuaire lit en diagonale.*"""
        # ⚠️ Plutot que de simuler openpyxl, on lit la table AU SOURCE : c'est
        # elle qui decide, et elle est deterministe.
        source = inspect.getsource(_kpi)
        table = re.search(r'_MOT_RAG = (\{[^}]*\})', source, re.DOTALL)
        self.assertIsNotNone(table, 'la table des mots a disparu de `_kpi`')
        mots = ast.literal_eval(table.group(1))
        self.assertEqual(set(mots), {'VERT', 'AMBRE', 'ROUGE'})
        self.assertIn('Non conforme', mots['ROUGE'])
        self.assertNotIn('Attention', mots['ROUGE'],
                         '« Attention » est plus faible que « À surveiller »')
        # ⚠️ Et le GLYPHE vient de la source unique, plus d'un litteral local.
        self.assertNotIn('"✓"', source)
        self.assertIn('glyphe_rag', source)
        self.assertEqual(GLYPHE_RAG_EXCEL['ROUGE'], '✗')
        print(f"    TRI-6 services/C9 : ROUGE = {mots['ROUGE']!r} domine "
              f"AMBRE = {mots['AMBRE']!r}, glyphe pris a la source")

    def test_second_sens_CONFIG_PLOTLY_porte_bien_ce_que_l_app_omet(self):
        """⚠️⚠️ SECOND SENS DU CONSTAT LAISSE OUVERT. `charts/C8` disait
        « Meme valeur aujourd'hui » : c'est REFUTE. Si un jour les deux
        coincident vraiment, ce controle tombera -- et ce sera le signal que
        le constat peut etre reecrit."""
        self.assertIn('responsive', CONFIG_PLOTLY)
        self.assertTrue(CONFIG_PLOTLY['responsive'])
        app = (_RACINE / 'actuaria_app.py').read_text(encoding='utf-8')
        litteraux = re.findall(r'config=\{[^}]*\}', app)
        self.assertTrue(litteraux, 'plus aucun literal de config dans l app')
        self.assertTrue(
            all('responsive' not in x for x in litteraux),
            "l'app declare desormais `responsive` : les deux valeurs "
            "coincident, `charts/C8` doit etre reecrit")
        print(f"    TRI-8 charts/C8 (OUVERT, app hors perimetre) : "
              f"{len(litteraux)} litteral(aux) sans `responsive`, "
              f"CONFIG_PLOTLY l'a")


if __name__ == '__main__':
    unittest.main()
