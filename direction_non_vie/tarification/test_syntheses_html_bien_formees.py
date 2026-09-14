r"""
==============================================================================
  LE HTML QUI PART AU CAC SE FERME DANS L'ORDRE
==============================================================================

⚠️⚠️ `RET-D1` -- `_md_to_html_light` ETAIT LA CONVERSION LOCALE que
`rapport_modeles_tarif` avait retiree au lot T6, avec ce motif : *<< elle
enveloppait les `<li>` dans un `<ul>` par une substitution de regex, puis
passait chaque LIGNE au decoupeur de paragraphes -- la balise `</ul>` se
retrouvait donc A L'INTERIEUR d'un `<p>` >>*. La meme fonction vivait
toujours ici.

Elle traite le commentaire actuariel du par. 7 ET chaque ligne de
`_syntheses_html` -- c'est-a-dire **chaque synthese reglementaire
publiee au CAC**.

Mesure du 14/09/2026, les neuf formes EN CONTEXTE DE DOCUMENT (une
phrase avant, une phrase apres) :

    conversion locale   2 fautes de balisage, 5 formes sur 9 BRUTES
                        (`#`, `##`, `>`, `---`, `|`)
    `core.narration`    0 faute,              1 forme sur 9 BRUTE (`>`)

La faute, mot pour mot : `</ul> ferme alors que <p> est ouvert`.

⚠️⚠️ MA PREMIERE SONDE AVAIT ACQUITTE A TORT. Sa liste d'essai ne
contenait qu'une liste SEULE -- le seul cas ou ce defaut ne se voit pas,
car `<ul><li>a</li><li>b</li></ul>` est bien forme. *Le defaut demande
une liste SUIVIE de quelque chose.* Quand un compte contredit celui d'un
auditeur, la methode a suspecter est la MIENNE.

⚠️ CE QUI BOUGE VISIBLEMENT : le titre `par. N -` passe de
`<h4 class="s-head">` a `<h3 class="s-head">` -- MEME classe, niveau
different. Mesure : la feuille de style de CE rapport (1 903 caracteres)
ne porte de regle ni pour `h3`, ni pour `h4`, ni pour `.s-head` ; seules
`h1` et `.header h1` y sont definies. Ni l'un ni l'autre n'etait stylé.
`SY-4` publie ce constat sans le fermer.
==============================================================================
"""
from __future__ import annotations

import ast
import html
import logging
import os
import pathlib
import re
import sys
import unittest
import warnings

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from core import narration as _md
from direction_non_vie.tarification.services import rapport_equipe_tarif as RE

_SOURCE = (_RACINE / 'direction_non_vie' / 'tarification' / 'services'
           / 'rapport_equipe_tarif.py')

#: ⚠️ CHAQUE FORME EST MISE EN CONTEXTE DE DOCUMENT -- une phrase avant,
#: une phrase apres. C'est ainsi qu'elles arrivent dans une synthese, et
#: c'est la seule mise en scene ou le defaut se voit.
_FORMES = {
    'titre #': '# Titre un',
    'titre ##': '## Titre deux',
    'titre ###': '### Titre trois',
    'gras **': 'texte **en gras** ici',
    'italique *': 'texte *en italique* ici',
    'liste -': '- premier\n- second',
    'citation >': '> une citation',
    'regle ---': '---',
    'tableau |': '| a | b |\n|---|---|\n| 1 | 2 |',
}
_MARQUEURS = {'titre #': '#', 'titre ##': '##', 'titre ###': '###',
              'gras **': '**', 'italique *': '*', 'liste -': '- ',
              'citation >': '>', 'regle ---': '---', 'tableau |': '|'}
#: `>` reste brut chez les DEUX : ce n'est pas une regression, et on le dit
#: plutot que de l'enfler.
_BRUTES_ADMISES = {'citation >'}
_VIDES = ('br', 'hr', 'img', 'meta', 'input', 'col', 'link')


def _en_contexte(corps: str) -> str:
    return f"Phrase avant.\n\n{corps}\n\nPhrase apres."


def _fautes_de_balisage(html: str) -> list:
    """Les balises se ferment-elles dans l'ORDRE ou elles sont ouvertes ?"""
    pile, fautes = [], []
    for m in re.finditer(r'</?([a-z][a-z0-9]*)[^>]*?(/?)>', html):
        nom, auto = m.group(1), m.group(2)
        if auto or nom in _VIDES:
            continue
        if m.group(0).startswith('</'):
            if not pile:
                fautes.append(f'</{nom}> sans ouverture')
            elif pile[-1] != nom:
                fautes.append(f'</{nom}> ferme alors que <{pile[-1]}> '
                              f'est ouvert')
                if nom in pile:
                    while pile and pile.pop() != nom:
                        pass
            else:
                pile.pop()
        else:
            pile.append(nom)
    return fautes + [f'<{x}> jamais ferme' for x in pile]


class TestSynthesesHtmlBienFormees(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._journal = logging.getLogger()
        cls._niveau = cls._journal.level
        cls._journal.setLevel(logging.CRITICAL)
        warnings.filterwarnings('ignore')

    @classmethod
    def tearDownClass(cls):
        cls._journal.setLevel(cls._niveau)

    # ── SY-1 ─────────────────────────────────────────────────────────────
    def test_SY1_AUCUNE_faute_de_balisage_sur_les_neuf_formes(self):
        """⚠️ LA MESURE PORTE SUR L'EMPILEMENT, pas sur la presence d'une
        balise : `</ul>` a l'interieur d'un `<p>` ouvre et ferme bien les
        deux, et un controle qui compterait les balises passerait."""
        vues = {}
        for nom, corps in _FORMES.items():
            f = _fautes_de_balisage(RE._md_to_html_light(_en_contexte(corps)))
            if f:
                vues[nom] = f
        self.assertEqual(
            vues, {},
            f"le HTML publie aux syntheses reglementaires est MALFORME : "
            f"{vues}. Ces lignes partent au commissaire aux comptes.")
        print(f"    SY-1 SCEAU : 0 faute sur {len(_FORMES)} formes en "
              f"contexte de document")

    # ── SY-2 ─────────────────────────────────────────────────────────────
    def test_SY2_les_formes_de_markdown_ne_sortent_plus_BRUTES(self):
        """⚠️ `>` RESTE BRUT CHEZ LES DEUX CONVERTISSEURS : on l'admet
        NOMMEMENT plutot que d'enfler le constat. Toute AUTRE forme brute
        est une regression."""
        brutes = {nom for nom, corps in _FORMES.items()
                  if _MARQUEURS[nom] in RE._md_to_html_light(
                      _en_contexte(corps))}
        surprise = sorted(brutes - _BRUTES_ADMISES)
        self.assertEqual(
            surprise, [],
            f"{len(surprise)} forme(s) sortent BRUTES du convertisseur : "
            f"{surprise}. Elles etaient 5 sur 9 avant ce lot.")
        print(f"    SY-2 SCEAU : {len(brutes)} brute(s), toutes admises "
              f"({sorted(brutes)})")

    # ── SY-3 ─────────────────────────────────────────────────────────────
    def test_SY3_le_corps_DELEGUE_et_ne_reimplemente_rien(self):
        """⚠️⚠️ LE CONSTAT EST UNE SECONDE IMPLEMENTATION, pas un bug de
        regex : le fermer en corrigeant la regex l'aurait rouvert au lot
        suivant. On interdit donc la FORME -- toute conversion markdown
        locale dans ce fichier."""
        self.assertEqual(
            RE._md_to_html_light('- a\n- b'), _md.en_html('- a\n- b'),
            "le convertisseur local ne rend plus ce que rend la source "
            "unique : une seconde redaction est revenue.")
        self.assertEqual(RE._md_to_html_light(''), '',
                         "l'entree vide ne rend plus la chaine vide")
        #: ⚠️⚠️ LE RELEVE EST PAR AST, ET C'EST UNE LECON PAYEE DEUX FOIS.
        #: Une premiere version balayait les LIGNES du fichier : elle a mordu
        #: sur la DOCSTRING de ce correctif, qui CITE `<h4 class=` pour
        #: expliquer ce qui a change. *MENTION prise pour USAGE.* On compte
        #: donc les APPELS de substitution qui FABRIQUENT une balise de bloc.
        #: ⚠️⚠️ ON VISE L'OPERATION, JAMAIS L'ALIAS -- lecon payee par un
        #: plant resté VERT. Une premiere version exigeait que l'appel
        #: s'ecrive `re.sub` ; le plant ecrivait `_r2.sub` et passait.
        #: *Un ensemble ferme de noms exacts est un releve PAR SYMBOLE
        #: deguise en AST.* On retient donc tout appel dont la METHODE est
        #: `sub`/`subn`, quel que soit le module qui la porte, plus la forme
        #: nue issue d'un `from re import sub`.
        arbre = ast.parse(_SOURCE.read_bytes().decode('utf-8'))
        interdits = []
        for n in ast.walk(arbre):
            if not isinstance(n, ast.Call):
                continue
            cible = n.func
            nom = (cible.attr if isinstance(cible, ast.Attribute)
                   else cible.id if isinstance(cible, ast.Name) else '')
            if nom not in ('sub', 'subn'):
                continue
            litteraux = [a.value for a in n.args
                         if isinstance(a, ast.Constant)
                         and isinstance(a.value, str)]
            if any(re.search(r'<(ul|li|h[1-6]|p)\b', x) for x in litteraux):
                interdits.append((n.lineno, ast.unparse(n)[:60]))
        self.assertEqual(
            interdits, [],
            f"une conversion markdown locale est revenue dans ce fichier : "
            f"{interdits}. Elle vit dans `core.narration`, et nulle part "
            f"ailleurs.")
        print(f"    SY-3 SCEAU : le corps delegue, 0 fabrique de balise "
              f"locale dans {_SOURCE.name}")

    # ── SY-4 ─────────────────────────────────────────────────────────────
    def test_SY4_la_classe_publiee_et_la_feuille_de_style_CONSTAT_ouvert(
            self):
        """⚠️ CE CONTROLE NE FERME RIEN : il MESURE et PUBLIE. Le titre de
        section porte `class="s-head"`, et la feuille de style de CE
        rapport n'en definit aucune regle -- celle qui existe
        (`.narration h3.s-head`) vit dans la feuille du JUMEAU. Le jour ou
        quelqu'un l'ajoute ici, ce controle le dira."""
        texte = _SOURCE.read_bytes().decode('utf-8')
        i = texte.find('<style>')
        j = texte.find('</style>', i)
        feuille = texte[i:j] if i >= 0 else ''
        self.assertTrue(feuille, "ce rapport n'a plus de feuille de style")
        rendu = _md.en_html('§7 — Commentaire actuariel')
        self.assertIn(
            's-head', rendu,
            "la source unique ne publie plus la classe de section : le "
            "constat ci-dessous ne porte plus sur rien")
        regle = 's-head' in feuille
        print(f"    SY-4 RELEVE (non ferme) : la classe `s-head` est "
              f"publiee, regle CSS dans CETTE feuille : "
              f"{'OUI' if regle else 'NON'} ({len(feuille)} car.)")

    # ── SY-5 ─────────────────────────────────────────────────────────────
    def test_SY5_les_DEUX_appelants_internes_tiennent_toujours(self):
        """⚠️ L'ASSIETTE DU CONSTAT : deux appelants, et ce sont eux qui
        publient au CAC. Si l'un disparaissait, ce sceau surveillerait une
        fonction que plus rien n'emprunte."""
        arbre = ast.parse(_SOURCE.read_bytes().decode('utf-8'))
        appels = [n.lineno for n in ast.walk(arbre)
                  if isinstance(n, ast.Call)
                  and ast.unparse(n.func).endswith('_md_to_html_light')]
        self.assertEqual(
            len(appels), 2,
            f"ce fichier ne porte plus DEUX appelants mais {len(appels)} "
            f"({appels}) : l'assiette de ce sceau a change.")
        #: et la synthese reellement produite est bien formee
        #: ⚠️ LA CLE DOIT ETRE UNE CLE REELLE : `_syntheses_html` n'itere pas
        #: le dictionnaire recu, il itere `_LABELS_SYNTHESES`. Une cle
        #: inventee rend une table VIDE, et ce controle mesurerait 15
        #: caracteres de balises au lieu d'une synthese.
        rendu = RE._syntheses_html({'qualite': '- un\n- deux\n\nApres.'})
        self.assertEqual(
            _fautes_de_balisage(rendu), [],
            f"la synthese reglementaire produite est MALFORMEE : "
            f"{_fautes_de_balisage(rendu)}")
        print(f"    SY-5 SCEAU : 2 appelants, synthese produite bien "
              f"formee ({len(rendu)} car.)")


    # ── SY-6 ─────────────────────────────────────────────────────────────
    def test_SY6_un_seuil_ecrit_avec_un_CHEVRON_ne_tronque_plus_la_phrase(
            self):
        """⚠️⚠️ LE PLUS GRAVE DE CE LOT, ET L'AUDITEUR NE LE DECRIT PAS.
        L'ancien corps n'ECHAPPAIT pas le `<` : dans
        `Gini = 0.1034 < 0.15 - pouvoir discriminant insuffisant`, tout ce
        qui suit le chevron etait avale comme une BALISE.

        Mesure du 14/09/2026 sur la phrase reelle du gel : un navigateur en
        lisait **59 caracteres sur 184**, et TROIS des quatre causes qui
        empechent le statut VERT ne s'affichaient jamais. *Un document qui
        part au commissaire aux comptes sous-disait son alarme.*

        `core/conformite_reglementaire.py` porte SIX litteraux de la forme
        `... < <chiffre>` : ce n'etait pas un cas isole."""
        phrase = ("STATUT AMBRE - 4 cause(s) empechent le VERT : "
                  "Gini = 0.1034 < 0.15 - pouvoir discriminant "
                  "insuffisant. Le backtesting walk-forward a ete conduit "
                  "et son resultat n'est pas satisfaisant.")
        rendu = RE._md_to_html_light(phrase)
        #: ce qu'un navigateur AFFICHE : les balises sont otees
        vu = html.unescape(re.sub(r'<[^>]*>', '', rendu)).strip()
        self.assertEqual(
            vu, phrase,
            f"la phrase est TRONQUEE a la publication : {len(vu)} "
            f"caractere(s) lus sur {len(phrase)}. Ce qui suit le premier "
            f"chevron est avale comme une balise.\n  lu : {vu!r}")
        self.assertIn(
            '&lt;', rendu,
            "le chevron n'est pas echappe : il le sera par accident le jour "
            "ou la phrase changera de forme")
        print(f"    SY-6 SCEAU : {len(vu)}/{len(phrase)} caracteres lus, "
              f"chevron echappe")


if __name__ == '__main__':
    unittest.main(verbosity=2)
