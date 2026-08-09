# -*- coding: utf-8 -*-
"""Tests T6 — la narration analysée une fois, rendue dans les deux formats.

⚠️ GATE : `py -m unittest discover -s core -t .` — voir test_frontiere_llm.py.
"""
import re
import unittest

from core.narration import (
    CITATION, CONSIGNE_MARKDOWN_RESTREINT, GENRES, MARQUEURS_AUTORISES,
    MARQUEURS_INTERDITS, PARAGRAPHE, PUCE, REGLE, SECTION, TABLEAU, TITRE1,
    TITRE2, TITRE3, analyser, en_html, segments)

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
    """T4 — ceinture ET bretelles, et la ceinture vient en premier.

    ⚠️ CE VERROU A CHANGÉ D'OBJET, ET LA MESURE L'A DÉCIDÉ. La consigne
    interdisait TOUT marqueur : la conversion ne laissait plus rien passer —
    zéro marqueur brut sur 13 748 caractères — mais le commentaire était
    devenu un mur de prose, 36 paragraphes sans un sous-titre ni une liste.
    Trois marqueurs sont rouverts ; le verrou vérifie désormais que la
    consigne et la chaîne de rendu disent EXACTEMENT la même chose.
    """

    def test_la_consigne_nomme_ce_qu_elle_autorise_ET_ce_qu_elle_interdit(self):
        for marqueur, _ in MARQUEURS_AUTORISES:
            self.assertIn(marqueur, CONSIGNE_MARKDOWN_RESTREINT, marqueur)
        for marqueur in MARQUEURS_INTERDITS:
            self.assertIn(marqueur, CONSIGNE_MARKDOWN_RESTREINT, marqueur)
        # ⚠️ ET LE COMPTE EST CELUI DE LA TABLE, pas un mot écrit à côté.
        self.assertIn('%d marqueurs' % len(MARQUEURS_AUTORISES),
                      CONSIGNE_MARKDOWN_RESTREINT)
        print('    OK T4 : %d marqueurs autorisés, %d interdits, tous nommés'
              % (len(MARQUEURS_AUTORISES), len(MARQUEURS_INTERDITS)))

    def test_AUCUN_marqueur_autorise_n_est_aussi_interdit(self):
        """⚠️ UNE CONSIGNE QUI SE CONTREDIT NE DIT RIEN. « ## » est autorisé
        et « ### » interdit : la vérification porte sur les libellés exacts,
        pas sur une inclusion de chaînes."""
        autorises = {m for m, _ in MARQUEURS_AUTORISES}
        self.assertEqual(autorises & set(MARQUEURS_INTERDITS), set())
        print('    OK T4b : aucun marqueur des deux côtés')

    def test_TOUT_CE_QUI_EST_AUTORISE_EST_REELLEMENT_CONVERTI(self):
        """⚠️ LE POINT DU LOT. Un marqueur autorisé mais non converti
        reviendrait au défaut de départ : il se lirait en clair dans un
        rapport signé."""
        attendus = {'##': TITRE2, '-': PUCE}
        for marqueur, genre in attendus.items():
            blocs = analyser('%s un texte' % marqueur)
            self.assertEqual(len(blocs), 1, marqueur)
            self.assertEqual(blocs[0].genre, genre, marqueur)
            self.assertEqual(blocs[0].texte, 'un texte', marqueur)
        # le gras n'est pas un bloc mais un passage
        segs = segments('un **terme** en valeur')
        self.assertEqual([s.texte for s in segs if s.gras], ['terme'])
        print('    OK T4c : les 3 marqueurs autorisés sont convertis')

    def test_les_marqueurs_autorises_se_VOIENT_dans_le_rendu(self):
        """⚠️ « CONVERTI » NE SUFFIT PAS : un « ### » devient un `<h5>` que
        rien ne style — le lecteur verrait un titre qui n'en a pas l'air.
        C'est pourquoi « ### » reste interdit alors que la conversion sait le
        traiter."""
        html = en_html('## Un sous-titre\n- une puce\nun **terme** fort')
        self.assertIn('<h4>Un sous-titre</h4>', html)
        self.assertIn('<ul>', html)
        self.assertIn('<li>une puce</li>', html)
        self.assertIn('<strong>terme</strong>', html)
        # et le rapport STYLE bien ces trois-là
        from direction_non_vie.tarification.services.rapport_modeles_tarif \
            import export_html
        rendu = export_html({}, {}, {'branche': 'auto'}, 'C', '31/12/2025',
                            'T4', narration_calculee=('Texte.', 'temoin'))
        style = rendu.split('<style>')[1].split('</style>')[0]
        for regle in ('.narration h4', '.narration ul'):
            self.assertIn(regle, style, regle)
        print('    OK T4d : sous-titre, liste et gras sont rendus ET stylés')

    def test_ce_qui_reste_interdit_l_est_pour_une_raison_de_RENDU(self):
        """⚠️ LA CONVERSION SAIT LES TRAITER — c'est le RENDU qui manque.
        Elle reste la ceinture : un marqueur glissé malgré la consigne ne se
        lira jamais en clair."""
        for source, genre in (('### titre', TITRE3), ('> citation', CITATION),
                              ('---', REGLE), ('| a | b |', TABLEAU)):
            blocs = analyser(source)
            self.assertEqual(blocs[0].genre, genre, source)
        html = en_html('### interdit\n> aussi\n---')
        for brut in ('###', '&gt;', '---'):
            self.assertNotIn(brut, html, brut)
        print('    OK T4e : les interdits restent convertis — la ceinture '
              'tient')

    def test_le_prompt_du_rapport_porte_la_consigne_restreinte(self):
        from direction_non_vie.tarification.services.rapport_modeles_tarif \
            import SYSTEM_PROMPT_TARIF as P
        self.assertIn(CONSIGNE_MARKDOWN_RESTREINT, P)
        self.assertNotIn('{CONSIGNE_MARKDOWN}', P)
        self.assertNotIn('AUCUN marqueur Markdown', P)
        # la consigne du prompt est bien celle CONSTRUITE depuis les tables
        for marqueur, _ in MARQUEURS_AUTORISES:
            self.assertIn('« %s »' % marqueur, P, marqueur)
        # ⚠️ ET LA RÈGLE 0 NE REDEMANDE PAS CE QUE LA CONSIGNE INTERDIT :
        # tout « ### » du prompt doit être dans la liste des interdits.
        for m in re.finditer(r'###', P):
            self.assertIn('INTERDIT', P[max(0, m.start() - 300):m.start()])
        print('    OK T4f : le prompt porte la consigne restreinte, sans se '
              'contredire')


if __name__ == '__main__':
    unittest.main(verbosity=2)
