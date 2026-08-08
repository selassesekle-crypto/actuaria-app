# -*- coding: utf-8 -*-
"""Tests T6 — la narration analysée une fois, rendue dans les deux formats.

⚠️ GATE : `py -m unittest discover -s core -t .` — voir test_frontiere_llm.py.
"""
import re
import unittest

from core.narration import (
    CITATION, CONSIGNE_SANS_MARKDOWN, GENRES, PARAGRAPHE, PUCE, REGLE,
    SECTION, TABLEAU, TITRE1, TITRE2, TITRE3, analyser, en_html, segments)

# Les neuf formes rencontrées, chacune avec le genre qu'elle doit produire.
FORMES = [
    ('# Titre', TITRE1), ('## Sous-titre', TITRE2), ('### Detail', TITRE3),
    ('§4 — COMPARAISON', SECTION), ('- un point', PUCE),
    ('| A | B |', TABLEAU), ('> une citation', CITATION),
    ('---', REGLE), ('du texte ordinaire', PARAGRAPHE),
]


class T1_LesNeufFormes(unittest.TestCase):
    """T1 — mesuré avant ce lot : le HTML en traitait 3 sur 7, le Word AUCUNE.

    ⚠️ Le Word découpait sur « §N » et écrivait chaque ligne telle quelle :
    « # », « ## » et « --- » se lisaient en clair dans le commentaire
    actuariel d'un rapport signé.
    """

    def test_chaque_forme_produit_son_genre(self):
        for source, attendu in FORMES:
            blocs = analyser(source)
            self.assertEqual(len(blocs), 1, repr(source))
            self.assertEqual(blocs[0].genre, attendu, repr(source))
        print(f'    OK T1 : les {len(FORMES)} formes reconnues')

    def test_aucun_marqueur_ne_survit_au_rendu_HTML(self):
        html = en_html('\n'.join(s for s, _ in FORMES))
        for marqueur in ('# ', '## ', '### ', '- un', '| A', '---'):
            self.assertNotIn(marqueur, html, marqueur)
        print('    OK T1b : aucun marqueur brut dans l\'HTML')

    def test_le_texte_voulu_par_le_prompt_est_CONSERVE(self):
        """⚠️ ON RETIRE LES MARQUEURS, JAMAIS LE TEXTE. Le numéro de section
        fait partie de ce que le prompt impose — le lecteur s'y repère."""
        blocs = analyser('§4 — COMPARAISON DES MODÈLES')
        self.assertEqual(blocs[0].texte, '§4 — COMPARAISON DES MODÈLES')
        print('    OK T1c : « §4 — … » conservé, seuls les marqueurs partent')

    def test_les_genres_sont_un_vocabulaire_ferme(self):
        for source, _ in FORMES:
            for bloc in analyser(source):
                self.assertIn(bloc.genre, GENRES)
        self.assertEqual(len(GENRES), 9)
        print(f'    OK T1d : {len(GENRES)} genres, vocabulaire fermé')


class T2_LeHtmlEstBienForme(unittest.TestCase):
    """T2 — ⚠️ L'ANCIENNE CONVERSION PRODUISAIT UN HTML MALFORMÉ."""

    def test_la_balise_de_liste_ne_fuit_plus_dans_un_paragraphe(self):
        """Elle enveloppait les <li> par une regex, puis passait chaque LIGNE
        au découpeur de paragraphes : « </ul> » se retrouvait DANS un « <p> »."""
        html = en_html('- un\n- deux\n**gras** ensuite')
        self.assertEqual(html.count('<ul>'), html.count('</ul>'))
        self.assertEqual(html.count('<ul>'), 1)
        self.assertEqual(re.findall(r'<p>[^<]*</ul>', html), [])
        # la liste se ferme AVANT le paragraphe qui suit, pas dedans
        self.assertIn('</ul>\n<p>', html)
        print('    OK T2 : <ul> ouvert et fermé une fois, aucune fuite en <p>')

    def test_toutes_les_balises_ouvertes_sont_fermees(self):
        html = en_html('\n'.join(s for s, _ in FORMES))
        for balise in ('ul', 'li', 'p', 'h3', 'h4', 'h5', 'blockquote'):
            self.assertEqual(html.count(f'<{balise}>') + html.count(f'<{balise} '),
                             html.count(f'</{balise}>'), balise)
        print('    OK T2b : 7 balises, toutes appariées')

    def test_le_texte_du_modele_ne_peut_pas_injecter_de_balise(self):
        """⚠️ LE TEXTE VIENT D'UN MODÈLE et part dans un rapport signé."""
        html = en_html('Attention <script>alerte()</script> & suite')
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&amp;', html)
        print('    OK T2c : balises et esperluettes échappées')


class T3_LesPassagesPourLeWord(unittest.TestCase):
    """T3 — un .docx n'a pas de balises : il a des passages."""

    def test_le_gras_et_l_italique_deviennent_des_passages(self):
        segs = segments('Le portefeuille compte **12 000 contrats** dont *20 %*.')
        self.assertEqual([s.texte for s in segs if s.gras], ['12 000 contrats'])
        self.assertEqual([s.texte for s in segs if s.italique], ['20 %'])
        self.assertEqual(''.join(s.texte for s in segs),
                         'Le portefeuille compte 12 000 contrats dont 20 %.')
        print('    OK T3 : gras et italique isolés, texte intégralement conservé')

    def test_un_texte_sans_emphase_reste_un_seul_passage(self):
        self.assertEqual(len(segments('du texte simple')), 1)
        print('    OK T3b : un texte sans emphase ne se fragmente pas')


class T4_LaConsigneEnAmont(unittest.TestCase):
    """T4 — ceinture ET bretelles, et la ceinture vient en premier."""

    def test_la_consigne_nomme_les_neuf_marqueurs(self):
        for marqueur in ('#', '##', '###', '**', '*', '-', '|', '>', '---'):
            self.assertIn(marqueur, CONSIGNE_SANS_MARKDOWN, marqueur)
        print('    OK T4 : la consigne nomme les marqueurs qu\'elle interdit')

    def test_le_prompt_du_rapport_la_porte_et_ne_demande_plus_de_markdown(self):
        """⚠️ LA RÈGLE 0 DEMANDAIT « ### pour les sous-titres, **gras** pour
        les termes importants » — exactement les marqueurs qui ressortaient en
        clair dans le livrable."""
        from direction_non_vie.tarification.services.rapport_modeles_tarif \
            import SYSTEM_PROMPT_TARIF as P
        self.assertIn(CONSIGNE_SANS_MARKDOWN, P)
        self.assertNotIn('{CONSIGNE_MARKDOWN}', P)
        # les seuls « ### » et « ** » restants sont ceux que la consigne INTERDIT
        for m in re.finditer(r'###|\*\*', P):
            self.assertIn('AUCUN marqueur Markdown',
                          P[max(0, m.start() - 400):m.start()])
        print('    OK T4b : le prompt porte la consigne et ne demande plus de '
              'markdown')


if __name__ == '__main__':
    unittest.main(verbosity=2)
