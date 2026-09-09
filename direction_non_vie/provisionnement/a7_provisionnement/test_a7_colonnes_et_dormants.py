# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — CE QU'UN LIVRABLE PROMET SANS RIEN PORTER, ET CE QUI NE TOURNE JAMAIS
=============================================================================

 Six constats du lot 12, deux causes communes.

 PREMIERE CAUSE : UNE PLACE RESERVEE A UNE INFORMATION QUI N'ARRIVE PAS.

 · Le tableau des methodes du WORD portait une colonne « Score » qui valait
   « — » sur ses CINQ lignes, sur les trois dossiers mesures. Elle avait
   survecu au retrait de `scores_confiance`. Elle est retiree.

 · L'audit affirme la meme colonne morte « dans le HTML, le Word ET
   l'Excel ». MESURE : c'est vrai du seul tableau des methodes du Word. Dans
   le HTML, la meme colonne porte « AIC = -2M » sur la ligne Clark et
   « p = 0,6484 » sur le GLM Poisson APC — la statistique qui DISTINGUE la
   methode. Dans le tableau des HYPOTHESES du Word elle porte 69/100 pour H1
   et 0/100 pour H2. Dans l'Excel elle porte de vraies valeurs.
   J'avais commence par la supprimer partout sur la foi de cette phrase :
   T2 ci-dessous a rattrape mon propre correctif. La colonne du HTML est
   RENOMMEE « Détail » ; les deux autres restent.

 · Le classeur annoncait « BEST ESTIMATE S2 (Art. 77) » sur une valeur
   BRUTE. L'actualisation a la courbe RFR est operee EN AVAL par A10 : le
   HTML, le Word et le commentaire le disent tous les trois. Le classeur
   etait le seul des quatre a promettre S2, et c'est le format qu'on ouvre
   pour recopier un chiffre dans un etat reglementaire.

 · `export_html` acceptait des dictionnaires VIDES et rendait 41 368
   caracteres de rapport a zero euro, sans le mot « echec » nulle part.

 SECONDE CAUSE : UN MECANISME ECRIT, TESTE, ET QUE PERSONNE N'APPELLE.

 · `methodes_demandees` existe pour que N1 previenne DES LA PREPARATION que
   Bornhuetter-Ferguson et Cape Cod ne pourront pas tourner faute
   d'exposition. Il n'etait jamais transmis. Il l'est.

 · `biais_recentrage_pct` etait calcule par le Bootstrap et jete. Il devient
   une recommandation au-dela du repere de 2,5 % du guide.

 · `seuil_llt` et `ruptures_calendaires` restent DORMANTS — il leur manque
   une valeur que seul l'actuaire peut fixer. Ils sont DECLARES tels quels
   dans le code, et T6 verifie que la declaration reste VRAIE : le jour ou
   quelqu'un les branche, ce test rougit pour que la prose suive. Il ne
   demande pas de les brancher.

 CE QUE CE FICHIER SCELLE, ET CE QU'IL NE SCELLE PAS. T2 ne lit pas le
 source : il compte les cellules du document PRODUIT. C'est lui qui a
 trouve que ma correction laissait, DANS LE HTML, cinq en-tetes pour des
 lignes de quatre cellules — les methodes informatives gardaient la
 cinquieme quand les methodes principales l'avaient perdue.

 ⚠️ IL N'AURAIT PAS TROUVE LE MEME DEFAUT DANS LE WORD, et je l'avais
 d'abord ecrit le contraire. Replante, ce defaut-la ne rougit pas : `_tbl`
 TRONQUE silencieusement les cellules excedentaires et le document sort
 avec quatre colonnes propres. Le defaut du Word a ete trouve en LISANT le
 source. Ce que T2 attrape dans le Word, c'est la raggedite ENTRE lignes,
 qui elle corrompt le fichier -- pas l'ecart entre en-tetes et cellules.
=============================================================================
"""
import ast
import io
import os
import unittest
from html.parser import HTMLParser

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement import n5_rapport as R
from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement,
)
from direction_non_vie.provisionnement.a7_provisionnement.n4_best_estimate import (
    BestEstimateS2,
)
from direction_non_vie.provisionnement.a7_provisionnement.n5_rapport import (
    MARQUEUR_ECHEC_RAPPORT,
)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS,
    RAA,
)

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.abspath(os.path.join(_ICI, '..', '..', '..'))

# Ce qu'une cellule peut porter sans rien dire.
VIDE = ('—', '-', '', '–', 'n/a', 'N/A')

_CACHE = {}


def _src(*bouts):
    return open(os.path.join(*bouts), encoding='utf-8').read()


def _run(C, primes=False, **kw):
    src = np.asarray(C, dtype=float)
    d = dict(source=src, mode_declare='cumule', generer_graphiques=False,
             generer_word=False, generer_html=False, n_sim_bootstrap=60,
             seed=42)
    if primes:
        d['primes'] = np.full(src.shape[0], float(np.nanmean(src[:, 0])) * 8.0)
    d.update(kw)
    return AgentA7Provisionnement(verbose=False).run(**d)


def _args(r):
    return (r['n1'], r['n2'], r['n3'], r['n4'], r.get('n5') or {})


class _Tables(HTMLParser):
    """Les tableaux d'un document, colspan compris.

    ⚠️ ECRIT APRES DEUX EXPRESSIONS REGULIERES QUI SE CONTREDISAIENT sur le
    meme document : l'une comptait six cellules la ou l'autre en comptait
    cinq, et je n'avais aucun moyen de savoir laquelle avait raison. Un
    invariant de structure ne vaut que ce que vaut l'instrument qui le
    mesure, donc l'instrument est un analyseur et non un motif.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self._pile, self._ligne, self._cell = [], [], None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'table':
            self._pile.append({'th': [], 'tr': []})
        elif tag == 'tr' and self._pile:
            self._ligne = []
        elif tag in ('td', 'th') and self._pile:
            self._cell = [tag, '', int(a.get('colspan', 1) or 1)]

    def handle_data(self, d):
        if self._cell is not None:
            self._cell[1] += d

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self._cell is not None:
            t, txt, span = self._cell
            self._cell = None
            if not self._pile:
                return
            val = ' '.join(txt.split())
            if t == 'th':
                self._pile[-1]['th'].extend([val] * span)
            elif self._ligne is not None:
                self._ligne.extend([val] * span)
        elif tag == 'tr' and self._pile and self._ligne is not None:
            if self._ligne:
                self._pile[-1]['tr'].append(self._ligne)
            self._ligne = None
        elif tag == 'table' and self._pile:
            t = self._pile.pop()
            self.tables.append((t['th'], t['tr']))


def _tableaux_word(octets):
    from docx import Document
    doc = Document(io.BytesIO(octets))
    out = []
    for tb in doc.tables:
        entetes = [c.text.strip() for c in tb.rows[0].cells]
        lignes = [[c.text.strip() for c in row.cells] for row in tb.rows[1:]]
        if entetes and lignes:
            out.append((entetes, lignes))
    return out


def _documents():
    """Les deux dossiers, HTML et Word, produits UNE fois pour tout le
    fichier. Deux formes de triangle et les deux regimes d'exposition."""
    if not _CACHE:
        for nom, tri, expo in (('RAA sans exposition', RAA, False),
                               ('GenIns avec exposition', GENINS, True)):
            r = _run(tri, primes=expo)
            p = _Tables()
            p.feed(R.export_html(*_args(r), ref_client='sceau'))
            _CACHE[nom] = {
                'run': r,
                'HTML': [(e, l) for e, l in p.tables if e and l],
                'WORD': _tableaux_word(R.export_word(*_args(r),
                                                     ref_client='sceau')),
            }
    return _CACHE


# =============================================================================
#  T1 — AUCUNE COLONNE NE RESERVE UNE PLACE QU'ELLE NE REMPLIT JAMAIS
# =============================================================================

class T1_Aucune_Colonne_Morte(unittest.TestCase):
    """⚠️ L'ASSIETTE EST LE DOCUMENT PRODUIT, pas le source. Le tiret ecrit
    dans le code est parfois une valeur par defaut legitime ; une colonne
    morte, elle, ne se voit qu'une fois le document fini."""

    def test_aucun_tableau_ne_porte_de_colonne_entierement_vide(self):
        mortes, n = [], 0
        for nom, doc in _documents().items():
            for fmt in ('HTML', 'WORD'):
                for entetes, lignes in doc[fmt]:
                    n += 1
                    for i, e in enumerate(entetes):
                        if all(len(l) > i and l[i] in VIDE for l in lignes):
                            mortes.append(
                                '%s / %s / tableau « %s » / colonne « %s » : '
                                '%d lignes, toutes vides'
                                % (nom, fmt, entetes[0], e, len(lignes)))
        self.assertEqual(mortes, [],
                         'Colonne(s) reservant une place sans jamais rien '
                         'porter :\n  ' + '\n  '.join(mortes))
        print('OK COL-1 : %d tableaux, aucune colonne morte' % n)

    def test_la_colonne_de_detail_du_html_porte_bien_quelque_chose(self):
        """⚠️ LE MIROIR DU PRECEDENT, ET IL COMPTE AUTANT. T1 interdit la
        colonne vide ; celui-ci interdit de SUPPRIMER une colonne qui porte.
        C'est l'erreur que j'ai commise en suivant l'audit a la lettre."""
        doc = _documents()['GenIns avec exposition']
        t = [x for x in doc['HTML'] if 'Poids BE' in x[0]]
        self.assertEqual(len(t), 1, 'tableau des methodes introuvable')
        entetes, lignes = t[0]
        self.assertIn('Détail', entetes,
                      'La colonne de detail du tableau des methodes a disparu. '
                      'Elle porte l AIC de Clark et le p du GLM Poisson APC : '
                      'ce ne sont pas des tirets.')
        self.assertNotIn('Score', entetes,
                         '« Score » etait le nom de `scores_confiance`, retire '
                         'avec l ancienne H3. Cette colonne porte un DETAIL, '
                         'pas une note.')
        i = entetes.index('Détail')
        pleines = [l[0] for l in lignes if len(l) > i and l[i] not in VIDE]
        self.assertTrue(pleines,
                        'Aucune ligne ne porte de detail : soit les methodes '
                        'informatives ont quitte le tableau, soit la colonne '
                        'est devenue morte et doit alors etre retiree.')
        print('OK COL-2 : « Détail » porte %d valeur(s)' % len(pleines))


# =============================================================================
#  T2 — AUTANT DE CELLULES QUE D'EN-TETES, SUR TOUS LES TABLEAUX
# =============================================================================

class T2_Largeur_Des_Tableaux(unittest.TestCase):
    """⚠️⚠️ LE CONTROLE QUI A RATTRAPE LE MIEN, DANS LE HTML. En retirant
    « Score » j'avais laisse leur cinquieme cellule aux lignes des methodes
    informatives -- Benktander, Clark, GLM Poisson APC -- pendant que les
    methodes principales n'en avaient plus que quatre. Le document sortait
    quand meme, sans erreur ni avertissement.

    ⚠️ CE CONTROLE NE COUVRE PAS LE MEME DEFAUT DANS LE WORD : `_tbl` y
    tronque les cellules en trop, et le tableau ressort coherent. Mesure
    faite en replantant la violation. Ce qu'il y attrape, c'est la
    raggedite ENTRE lignes, qui corrompt le fichier produit."""

    def test_chaque_ligne_a_autant_de_cellules_que_d_entetes(self):
        ecarts, n = [], 0
        for nom, doc in _documents().items():
            for fmt in ('HTML', 'WORD'):
                for entetes, lignes in doc[fmt]:
                    n += 1
                    for l in lignes:
                        if len(l) != len(entetes):
                            ecarts.append(
                                '%s / %s / tableau « %s » : %d en-tetes mais '
                                'une ligne de %d cellules (« %s »)'
                                % (nom, fmt, entetes[0], len(entetes), len(l),
                                   (l[0] or '?')[:30]))
                            break
        self.assertEqual(ecarts, [],
                         'Tableau(x) de largeur incoherente :\n  '
                         + '\n  '.join(ecarts))
        print('OK COL-3 : %d tableaux, largeur coherente partout' % n)


# =============================================================================
#  T3 — LE CLASSEUR NE PROMET PAS UNE ACTUALISATION QUI N'A PAS EU LIEU
# =============================================================================

class T3_L_Etiquette_Du_Best_Estimate(unittest.TestCase):

    def test_aucun_module_de_livrable_n_annonce_s2_sur_une_valeur_brute(self):
        """⚠️ TRACE AU SITE : le constat ne se ferme pas sur « le classeur est
        corrige » mais sur « les formats s'accordent ». Un format qui derive
        seul EST le defaut d'origine.

        ⚠️ L'ASSIETTE EXCLUT LES COMMENTAIRES : celui du classeur CITE
        l'ancienne etiquette pour dire ce qui a ete corrige, et la citer n'est
        pas la produire."""
        fautes = []
        for fichier in ('n5_excel.py', 'n5_rapport.py', 'n5_commentaire.py'):
            for i, l in enumerate(_src(_ICI, fichier).split(chr(10)), 1):
                if 'BEST ESTIMATE S2' in l and not l.lstrip().startswith('#'):
                    fautes.append('%s:%d %s' % (fichier, i, l.strip()[:90]))
        self.assertEqual(fautes, [],
                         'Un livrable promet « BEST ESTIMATE S2 » sur une '
                         'valeur brute. L actualisation S2 est operee en aval '
                         'par A10 :\n  ' + '\n  '.join(fautes))
        print('OK ETI-1 : les trois modules de livrable s accordent')


# =============================================================================
#  T4 — UN RUN SANS CALCUL NE PRODUIT PAS DE RAPPORT
# =============================================================================

class T4_La_Porte_D_Export(unittest.TestCase):

    def test_des_dictionnaires_vides_ne_fabriquent_pas_un_rapport(self):
        h = R.export_html({}, {}, {}, {}, {}, ref_client='sceau')
        self.assertTrue(h.startswith(MARQUEUR_ECHEC_RAPPORT),
                        'export_html a produit %d caracteres a partir de rien, '
                        'et sans marqueur d echec.' % len(h))
        self.assertLess(len(h), 2000,
                        'Le repli fait %d caracteres : ce n est plus un repli.'
                        % len(h))
        print('OK PORTE-1 : vide -> repli marque de %d caracteres' % len(h))

    def test_n1_seul_ne_suffit_pas_davantage(self):
        """N1 est un diagnostic de DONNEE, pas un calcul : un dossier qui n a
        que lui n a rien a publier."""
        r = _documents()['RAA sans exposition']['run']
        h = R.export_html(r['n1'], {}, {}, {}, {}, ref_client='sceau')
        self.assertTrue(h.startswith(MARQUEUR_ECHEC_RAPPORT),
                        'Un N1 seul a suffi a produire %d caracteres.' % len(h))
        print('OK PORTE-2 : N1 seul -> repli marque')

    def test_un_run_reel_traverse_la_porte(self):
        """⚠️ LE MIROIR : un garde-fou qui ferme TOUT ne garde rien. « Ce
        retrecissement laisse-t-il passer le travail reel ? » se pose au filet
        comme au correctif."""
        r = _documents()['RAA sans exposition']['run']
        h = R.export_html(*_args(r), ref_client='sceau')
        self.assertFalse(h.startswith(MARQUEUR_ECHEC_RAPPORT),
                         'Un run reel a ete refuse par la porte.')
        self.assertGreater(len(h), 20000)
        print('OK PORTE-3 : un run reel produit %d caracteres' % len(h))


# =============================================================================
#  T5 — CE QUE LE MODULE SAIT DE SES METHODES ATTEINT N1
# =============================================================================

class T5_Exposition_Annoncee_Des_La_Preparation(unittest.TestCase):

    @staticmethod
    def _alertes_primes(n1):
        return [str(a) for a in (n1.get('alertes') or [])
                if 'rimes absentes' in str(a)]

    def test_sans_exposition_la_preparation_nomme_les_methodes_bloquees(self):
        n1 = _documents()['RAA sans exposition']['run']['n1']
        al = self._alertes_primes(n1)
        self.assertTrue(
            al,
            'La preparation ne signale AUCUNE methode bloquee alors que '
            'l exposition est absente. `methodes_demandees` n atteint plus '
            '`preparer_triangles` : `primes_requises` retombe a False, '
            '`methodes_bloquees` a la liste vide, et le dossier sort VERT en '
            'attendant que N3 decouvre l indisponibilite beaucoup plus tard.')
        for m in ('bornhuetter_ferguson', 'cape_cod'):
            self.assertTrue(any(m in a for a in al),
                            '%s n est pas nommee parmi les methodes '
                            'bloquees :\n  %s' % (m, '\n  '.join(al)))
        self.assertEqual(
            n1.get('statut'), 'AMBRE',
            'Le statut N1 devrait passer AMBRE quand deux des quatre methodes '
            'principales sont bloquees ; il vaut %r.' % n1.get('statut'))
        print('OK EXPO-1 : N1 AMBRE, %d alerte(s) nommant les methodes' % len(al))

    def test_avec_exposition_rien_n_est_bloque(self):
        """⚠️ L'ASYMETRIE EST LE REVELATEUR LE MOINS CHER : un test qui ne
        verifie que le cas rouge ne distingue pas un mecanisme qui MARCHE d un
        mecanisme qui dit toujours non."""
        n1 = _documents()['GenIns avec exposition']['run']['n1']
        self.assertEqual(self._alertes_primes(n1), [],
                         'Des methodes sont declarees bloquees alors que '
                         'l exposition est fournie.')
        print('OK EXPO-2 : avec exposition, aucune methode bloquee')


# =============================================================================
#  T6 — LE BIAIS DE RECENTRAGE, ET LES DEUX MECANISMES DECLARES DORMANTS
# =============================================================================

class T6_Biais_Et_Dormants(unittest.TestCase):

    def test_un_recentrage_au_dela_du_repere_devient_une_recommandation(self):
        """⚠️ L'ASSIETTE EST LE SEUIL, DES DEUX COTES. On injecte 15,42 % — la
        valeur mesuree sur RAA — puis 1,0 %, sous le repere de 2,5 %. Un seuil
        qu'on ne verifie que par au-dessus peut etre un `if True`."""
        r = _documents()['RAA sans exposition']['run']
        C = np.asarray(RAA, dtype=float)

        def _reco(biais):
            n3b = dict(r['n3'])
            b = dict(n3b.get('bootstrap') or {})
            b['biais_recentrage_pct'] = biais
            n3b['bootstrap'] = b
            out = BestEstimateS2().calculer(r['n2'], n3b, C)
            return [str(x) for x in (out.get('recommandations') or [])
                    if 'Recentrage du Bootstrap' in str(x)]

        haut, bas = _reco(0.1542), _reco(0.010)
        self.assertTrue(
            haut,
            'Un recentrage de 15,42 % — six fois le repere de 2,5 % du guide '
            'IA 2023 — ne produit aucune recommandation. La grandeur est '
            'calculee par `bootstrap_odp`, publiee, et jetee.')
        self.assertIn('15.42', haut[0].replace(',', '.'),
                      'La recommandation ne porte pas la valeur mesuree :\n  '
                      + haut[0])
        self.assertEqual(
            bas, [],
            'Un recentrage de 1,0 %, SOUS le repere, produit tout de meme une '
            'recommandation : le seuil ne mord pas au bon endroit.')
        print('OK BIAIS-1 : 15,42 % signale, 1,0 % silencieux')

    def test_les_deux_declarations_de_dormance_restent_vraies(self):
        """⚠️⚠️ UN CONTROLE SUR UNE PROSE, ET IL L'ASSUME. `seuil_llt` et
        l'archivage scelle sont DECLARES dormants dans le code. Le jour ou
        quelqu'un les branche, ces phrases deviennent fausses et personne n a
        de raison de relire ces commentaires-la. Ce test rougit ce jour-la —
        pour que la prose suive, pas pour empecher le branchement."""
        r = _documents()['RAA sans exposition']['run']
        prep = r['n1'].get('preparation')
        self.assertIsNotNone(prep, 'la preparation complete n est plus jointe')
        self.assertIsNone(
            getattr(prep, 'separation', None),
            'La separation grands sinistres / attritionnels s est executee : '
            '`seuil_llt` a trouve un appelant. Le commentaire de '
            '`nv_triangle.py` qui la declare dormante doit etre corrige.')

        arbre = ast.parse(_src(_ICI, 'agent.py'))
        passe = [k.arg for n in ast.walk(arbre) if isinstance(n, ast.Call)
                 for k in n.keywords if k.arg == 'seuil_llt']
        self.assertEqual(passe, [],
                         '`agent.py` transmet desormais `seuil_llt`.')

        app = os.path.join(_RACINE, 'actuaria_app.py')
        if os.path.exists(app):
            n = _src(app).lower().count('archiv')
            self.assertEqual(
                n, 0,
                'L application mentionne « archiv » %d fois : l archivage '
                'scelle SHA-256 n est peut-etre plus dormant. Le commentaire '
                'de `agent.py` qui l affirme doit etre relu.' % n)
        print('OK DORM-1 : les declarations de dormance restent vraies')


# =============================================================================
#  T7 — LA DOCSTRING DU BOOTSTRAP NE RECOPIE PLUS SON DEFAUT
# =============================================================================

class T7_Le_Defaut_Nomme(unittest.TestCase):

    def test_la_docstring_nomme_la_constante_au_lieu_de_la_recopier(self):
        from direction_non_vie.provisionnement.a7_provisionnement.n3 import (
            bootstrap_odp as BO,
        )
        s = _src(_ICI, 'n3', 'bootstrap_odp.py')
        fn = next(n for n in ast.walk(ast.parse(s))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == 'bootstrap_odp')
        noms = [a.arg for a in fn.args.args]
        defauts = dict(zip(noms[len(noms) - len(fn.args.defaults):],
                           fn.args.defaults))
        self.assertEqual(ast.unparse(defauts['n_sim']), 'N_SIM_DEFAUT',
                         'Le defaut de `n_sim` n est plus la constante nommee.')
        doc = ast.get_docstring(fn) or ''
        self.assertIn('N_SIM_DEFAUT', doc,
                      'La docstring ne nomme pas la constante.')
        # ⚠️ L'ASSIETTE EXCLUT LA LIGNE QUI CITE L'ANCIEN ENONCE : la docstring
        # le rappelle pour dire ce qui a ete corrige. Le citer n est pas
        # l affirmer — meme distinction que dans T3.
        fautes = [l.strip() for l in doc.split(chr(10))
                  if 'défaut 1000' in l and 'ANNONCAIT' not in l]
        self.assertEqual(
            fautes, [],
            'La docstring annonce de nouveau un defaut recopie, alors que '
            'N_SIM_DEFAUT vaut %d :\n  %s'
            % (BO.N_SIM_DEFAUT, '\n  '.join(fautes)))
        print('OK DEF-1 : docstring -> N_SIM_DEFAUT (= %d)' % BO.N_SIM_DEFAUT)


if __name__ == '__main__':
    unittest.main(verbosity=2)
