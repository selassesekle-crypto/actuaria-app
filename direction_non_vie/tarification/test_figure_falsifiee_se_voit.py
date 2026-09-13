r"""
==============================================================================
  UNE FIGURE FALSIFIEE NE PASSE PLUS INAPERCUE AU GEL
==============================================================================

⚠️⚠️ CE QUE CE CONTROLE EXISTE POUR EMPECHER, ET C'EST L'INSTRUMENT DE
PREUVE LUI-MEME QUI ETAIT EN CAUSE. `contenu_html` appliquait
`_BALISE.sub('\n', texte)` AVANT toute comparaison : cela retire chaque
`<script>...</script>` en entier et toutes les balises avec leurs
attributs. Or les TROIS formes de figure d'une page de ce depot y vivent.
`contenu_docx`, lui, hachait deja ses images -- << LES FIGURES ENTRENT
DANS LA MESURE >>, dit son commentaire.

MESURE DU 11/09/2026, EN TROMPANT L'INSTRUMENT, texte visible strictement
identique :

    falsification                                  ecarts HTML   .docx
    courbe de lift inversee [0,05-0,31]->[9,90-1,10]     0          --
    valeur injectee dans le script (PRIME_REELLE)        0          --
    image PNG entierement remplacee                      0           1
    SVG inline remplace                                  0          --
    contre-epreuve : un centime du texte visible         1           1

*L'instrument n'etait pas casse : il etait ETROIT, et il ne disait pas
qu'il etait etroit.* Le piege des surfaces jumelles applique a la preuve.

⚠️⚠️ ET LA CONDITION QUI REND CE CORRECTIF ACCEPTABLE EST UN COMPORTEMENT,
PAS UNE INTENTION : hacher une figure NON DETERMINISTE ferait un rouge par
run, et le correctif serait alors PIRE que le defaut. Les identifiants de
`<div>` de Plotly sont tires au hasard a chaque rendu ; ils sont
neutralises avant hachage. **`FG-5` verifie ce sens-la, et sans lui ce
fichier n'attesterait qu'une moitie.**

CE QUE CES CONTROLES SURVEILLENT : le RESULTAT de la comparaison sur des
pages construites ici, jamais la presence d'une fonction. Une reecriture
correcte de la mesure doit rester verte ; un retour a l'aveuglement doit
rougir, quelle qu'en soit la cause.
==============================================================================
"""
from __future__ import annotations

import base64
import os
import pathlib
import sys
import unittest

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from direction_non_vie.tarification.services import (
    gel_livrables as G,
)

#: une charge PNG minuscule mais VALIDE, et sa jumelle differente
_PNG_A = base64.b64encode(bytes(range(90, 190))).decode()
_PNG_B = base64.b64encode(bytes(range(91, 191))).decode()
_SVG_A = '<svg viewBox="0 0 10 10"><path d="M0,0 L9,9"/></svg>'
_SVG_B = '<svg viewBox="0 0 10 10"><path d="M0,9 L9,0"/></svg>'

#: ⚠️ LE TEXTE VISIBLE EST LE MEME DANS TOUTES LES VARIANTES. C'est toute
#: la difficulte : un instrument qui ne regarde que le texte ne peut RIEN
#: voir de ce qui suit.
_TEXTE = ('<h1>Rapport de tarification</h1>'
          '<p>Prime pure moyenne : 344.99 EUR</p>'
          '<p>Portefeuille : 1 500 contrats</p>')


def _page(png=_PNG_A, svg=_SVG_A, courbe='[0.05, 0.18, 0.31]',
          script_extra='', texte=_TEXTE, uuid='d599714a-1111-2222-3333-'
                                               '444455556666'):
    """Une page portant LES TROIS voies de figure a la fois."""
    return (
        f'<html><body>{texte}'
        f'<div class="fig">{svg}</div>'
        f'<img src="data:image/png;base64,{png}">'
        f'<div id="{uuid}"></div>'
        f'<script>Plotly.newPlot("{uuid}", '
        f'[{{"y": {courbe}}}]);{script_extra}</script>'
        f'</body></html>').encode()


def _ecarts(a: bytes, b: bytes):
    return G.comparer(G.empreinte({'page': a}), G.empreinte({'page': b}))


class TestUneFigureFalsifieeSeVoit(unittest.TestCase):

    def test_FG1_SCEAU_une_PNG_remplacee_est_VUE(self):
        """⚠️⚠️ LA FALSIFICATION LA PLUS GROSSIERE, ET ELLE PASSAIT. Toute
        l'image remplacee, texte identique : zero ecart mesure le
        11/09/2026. Le meme dossier en .docx la voyait."""
        e = _ecarts(_page(), _page(png=_PNG_B))
        self.assertTrue(
            e,
            "une image PNG ENTIEREMENT remplacee ne produit aucun ecart : "
            "le gel certifie un document dont la figure a change.")
        print(f"    FG-1 SCEAU : PNG remplacee -> {len(e)} ecart(s)")

    def test_FG2_SCEAU_un_SVG_inline_remplace_est_VU(self):
        """⚠️⚠️ LA VOIE LA PLUS PROBABLE, ET CELLE QUE LE PREMIER CORRECTIF
        AVAIT OUBLIEE (`gel/C1b`). Son commentaire nommait deux voies -- la
        `<img data:>` et le repli `<script>` -- alors que `rendre_figure` en
        a TROIS, et que la premiere est le SVG inline des que `kaleido` est
        present. *L'assiette laissait dehors la figure la plus probable.*"""
        e = _ecarts(_page(), _page(svg=_SVG_B))
        self.assertTrue(
            e,
            "un SVG inline remplace ne produit aucun ecart : la voie de "
            "figure la PLUS EMPRUNTEE reste hors de la mesure.")
        print(f"    FG-2 SCEAU : SVG remplace -> {len(e)} ecart(s)")

    def test_FG3_SCEAU_une_courbe_INVERSEE_dans_le_script_est_VUE(self):
        """⚠️⚠️ CELLE QUI COUTE LE PLUS CHER A UN ACTUAIRE. Une courbe de
        lift inversee dit exactement le contraire de ce que le modele
        mesure, et le texte de la page ne bouge pas d'un caractere."""
        e = _ecarts(_page(), _page(courbe='[9.90, 3.40, 1.10]'))
        self.assertTrue(
            e,
            "une courbe de lift INVERSEE dans le script ne produit aucun "
            "ecart : le dossier signe peut affirmer l'inverse de sa mesure.")
        print(f"    FG-3 SCEAU : courbe inversee -> {len(e)} ecart(s)")

    def test_FG4_SCEAU_une_valeur_INJECTEE_dans_le_script_est_VUE(self):
        """⚠️ La forme la plus discrete : on n'altere rien de ce qui
        s'affiche, on AJOUTE une valeur dans le script."""
        e = _ecarts(_page(), _page(script_extra='var PRIME_REELLE=980.10;'))
        self.assertTrue(
            e,
            "une valeur injectee dans le script ne produit aucun ecart.")
        print(f"    FG-4 SCEAU : valeur injectee -> {len(e)} ecart(s)")

    def test_FG5_CONTRE_EPREUVE_une_figure_NON_DETERMINISTE_ne_rougit_pas(
            self):
        """⚠️⚠️ LA CONDITION QUI REND CE CORRECTIF ACCEPTABLE, ET C'EST UN
        COMPORTEMENT. Deux rendus de la MEME figure Plotly portent des
        identifiants de `<div>` DIFFERENTS -- mesure du 11/09 :
        `d599714a-...` puis `6d6c45fb-...`. Hacher le script brut ferait un
        ROUGE A CHAQUE RUN, *et un avertissement permanent est un
        avertissement qu'on cesse de lire.*"""
        e = _ecarts(_page(), _page(uuid='6d6c45fb-9999-8888-7777-666655554444'))
        self.assertEqual(
            [str(x) for x in e], [],
            f"deux rendus de la MEME figure, identifiants aleatoires "
            f"differents, produisent {len(e)} ecart(s) : le gel deviendrait "
            f"rouge a chaque execution et cesserait d'etre lu.")
        print("    FG-5 contre-epreuve : identifiants aleatoires -> 0 ecart")

    def test_FG6_CONTRE_EPREUVE_une_page_IDENTIQUE_rend_zero_ecart(self):
        """⚠️ Le sens le plus simple, et il se verifie quand meme : un
        instrument qui accuse tout n'atteste rien."""
        e = _ecarts(_page(), _page())
        self.assertEqual([str(x) for x in e], [],
                         'une page identique a elle-meme produit un ecart')
        print('    FG-6 contre-epreuve : page identique -> 0 ecart')

    def test_FG7_CONTRE_EPREUVE_un_centime_du_TEXTE_reste_vu(self):
        """⚠️⚠️ CE QUE LE CORRECTIF NE DOIT SURTOUT PAS PERDRE. En ajoutant
        les figures a la mesure, on change la FORME de ce qui est compare :
        si le texte en sortait, on aurait echange un aveuglement contre un
        autre. *Un correctif se verifie aussi sur ce qu'il ne devait pas
        toucher.*"""
        autre = _TEXTE.replace('344.99', '345.00')
        e = _ecarts(_page(), _page(texte=autre))
        self.assertTrue(
            e, "un centime change dans le texte visible n'est plus vu : le "
               "correctif a perdu ce que l'instrument savait deja faire.")
        #: ⚠️ et il doit etre vu DANS LE TEXTE, pas dans les figures
        ou = ' '.join(str(x.emplacement) for x in e)
        self.assertIn(
            'texte', ou,
            f"l'ecart de texte n'est pas rapporte dans le texte : {ou[:80]}")
        print(f"    FG-7 contre-epreuve : un centime -> {len(e)} ecart(s), "
              f"dans le texte")

    def test_FG9_CONTRE_EPREUVE_un_SVG_PLOTLY_rerendu_ne_rougit_pas(self):
        """⚠️⚠️ LA MEME CONDITION QUE `FG-5`, MAIS SUR LA FORME REELLE DU
        DEPOT -- et elle est DIFFERENTE. Le SVG de Plotly ne porte pas
        d'UUID : il porte un SEL de quelques caracteres hexadecimaux par
        figure (`id="defs-712aaa"`, `id="clip712aaax"`,
        `url(#legend712aaaxy)`) et un jeton par trace
        (`class="trace scatter tracee1fee"`).

        MESURE DU 13/09/2026, deux productions du meme jeu : **11 figures
        sur 11** dans `a6 HTML` et **13 sur 13** dans `rapport_modeles
        HTML` differaient, pour 13 488 caracteres identiques de part et
        d'autre. *Hacher le balisage brut aurait rendu le gel ROUGE A
        CHAQUE RUN -- exactement ce que le correctif devait eviter.*

        ⚠️ Neutraliser prefixe par prefixe ne suffisait pas : `defs-` et
        `clip` faisaient tomber 11 a 6, puis `legend` apparaissait, puis
        `trace`. *Une liste de prefixes est une liste a tenir ; la regle
        qui tient est qu'un identifiant genere n'est pas une donnee.*"""
        gabarit = ('<svg viewBox="0 0 9 9"><defs id="defs-{s}">'
                   '<clipPath id="clip{s}xy"><rect width="4" height="4"/>'
                   '</clipPath></defs>'
                   '<g class="trace scatter trace{t}" '
                   'clip-path="url(#clip{s}xyplot)">'
                   '<path d="M0,0 L7,7" style="fill: rgb(31, 46, 82);"/>'
                   '</g><g id="legend{s}"/></svg>')
        un = gabarit.format(s='712aaa', t='e1fee')
        deux = gabarit.format(s='bbe466', t='a39a3')
        self.assertNotEqual(un, deux, 'le gabarit ne varie pas : ce '
                                      'controle ne mesurerait rien')
        e = _ecarts(_page(svg=un), _page(svg=deux))
        self.assertEqual(
            [str(x) for x in e], [],
            f"deux rendus Plotly de la MEME figure produisent {len(e)} "
            f"ecart(s) : le gel deviendrait rouge a chaque execution sur "
            f"les 24 figures des deux rapports signes.")
        #: ⚠️ ET LE SECOND SENS, SUR LE MEME GABARIT : neutraliser les
        #: identifiants ne doit pas avoir efface la DONNEE.
        vrai = gabarit.format(s='712aaa', t='e1fee').replace(
            'M0,0 L7,7', 'M0,7 L7,0')
        e2 = _ecarts(_page(svg=un), _page(svg=vrai))
        self.assertTrue(
            e2,
            "une courbe INVERSEE dans le meme SVG n'est plus vue : la "
            "neutralisation des identifiants a emporte la donnee.")
        print(f"    FG-9 contre-epreuve : sel et trace Plotly -> 0 ecart, "
              f"trace inversee -> {len(e2)} ecart(s)")

    def test_FG8_SCEAU_les_TROIS_voies_sont_dans_la_mesure(self):
        """⚠️⚠️ LE COMPTE, ET IL SE MESURE. `gel/C1b` est ne d'une assiette
        qui nommait DEUX voies quand le code en a TROIS. On ne verifie donc
        pas << les figures sont mesurees >> en general : on exige que
        CHACUNE des trois, seule, produise un ecart."""
        voies = {
            'SVG inline': _page(svg=_SVG_B),
            'img data: PNG': _page(png=_PNG_B),
            'script Plotly': _page(courbe='[9.90, 3.40, 1.10]'),
        }
        muettes = [nom for nom, page in voies.items()
                   if not _ecarts(_page(), page)]
        self.assertEqual(
            muettes, [],
            f"ces voies de figure restent INVISIBLES au gel : {muettes}. "
            f"Une assiette qui en oublie une laisse passer la falsification "
            f"la plus probable.")
        print(f"    FG-8 SCEAU : les {len(voies)} voies de figure sont "
              f"dans la mesure")


if __name__ == '__main__':
    unittest.main(verbosity=2)
