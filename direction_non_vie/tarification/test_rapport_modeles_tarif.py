# -*- coding: utf-8 -*-
"""Tests T1 — une seule narration pour tous les formats du rapport tarif.

⚠️ POURQUOI CE FICHIER EXISTE. `rapport_modeles_tarif.py` produit un livrable
SIGNÉ — celui qui part chez un commissaire aux comptes — et n'avait aucun
test. Le défaut que T1 corrige a donc vécu jusqu'à ce qu'un rapport réel soit
regardé : mesuré, le HTML portait 18 089 caractères de commentaire actuariel
et le Word portait le dépôt technique de l'agent.

⚠️ AUCUN TEST D'ICI N'ATTEINT LE RÉSEAU : le client est simulé.
"""
import io
import os
import re
import sys
import unittest
import zipfile
from unittest.mock import patch

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)

from direction_non_vie.tarification.services import (  # noqa: E402
    rapport_modeles_tarif as R)

NARRATION = ('§1 — CONTEXTE ET QUALITE DES DONNEES\n'
             'Le portefeuille compte 12 000 contrats. Reference : Goldburd.\n'
             '§7 — CONCLUSION\nAvis favorable sous reserve.')

# Le repli : ce que le Word portait SEUL avant ce lot.
A3 = {'metriques': {'poisson': {'gini': 0.1775, 'aic': 10308}},
      'commentaire': 'REPLI AGENT'}
A4 = {'classement': [], 'commentaire': 'REPLI AGENT'}
A6 = {'branche': 'auto', 'statut_rag': 'VERT'}


class _Bloc:
    def __init__(self, texte):
        self.text, self.type = texte, 'text'


def _client_simule(appels, texte=NARRATION, echouer=False):
    """Un client `anthropic` de substitution qui compte les appels."""
    class _Messages:
        def create(self, **kw):
            appels.append(kw.get('model'))
            if echouer:
                raise RuntimeError('panne simulée du service')

            class _Reponse:
                content = [_Bloc(texte)]
            return _Reponse()

    class _Client:
        def __init__(self, **_):
            self.messages = _Messages()
    return _Client


def _texte_docx(octets):
    if not octets:
        return ''
    xml = zipfile.ZipFile(io.BytesIO(octets)).read(
        'word/document.xml').decode('utf-8')
    return re.sub(r'<[^>]+>', '', xml)


def _produire(appels, formats=('html', 'word'), echouer=False):
    with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'cle-de-test'}):
        with patch('anthropic.Anthropic',
                   _client_simule(appels, echouer=echouer)):
            rap = R.generer_rapport_tarification(
                A3, A4, A6, 'DEMO', '31/12/2025', 'T1', list(formats))
    return ((rap.get('html_bytes') or b'').decode('utf-8', 'replace'),
            _texte_docx(rap.get('word_bytes')))


class T1_UneSeuleNarration(unittest.TestCase):
    """T1 — le format qui part chez un commissaire doit porter le même
    commentaire que celui qu'on lit à l'écran."""

    def test_un_seul_appel_pour_les_deux_formats(self):
        """⚠️ DEUX AVANT CE LOT : `export_html` et `export_word` appelaient
        chacun la narration pour leur propre compte."""
        appels = []
        _produire(appels)
        self.assertEqual(len(appels), 1, f'appels : {appels}')
        print('    OK T1 : 1 appel pour html+word (2 avant ce lot)')

    def test_les_deux_formats_portent_le_MEME_commentaire(self):
        """⚠️ LE POINT DU LOT. Mesuré sur un rapport réel : le HTML portait la
        narration Claude, le Word le dépôt technique de l'agent."""
        html, word = _produire([])
        for marqueur in ('CONTEXTE ET QUALITE DES DONNEES', 'Goldburd',
                         'Avis favorable sous reserve'):
            self.assertIn(marqueur, html, f'HTML : {marqueur}')
            self.assertIn(marqueur, word, f'WORD : {marqueur}')
        # et AUCUN des deux ne retombe sur le dépôt de l'agent
        self.assertNotIn('REPLI AGENT', html)
        self.assertNotIn('REPLI AGENT', word)
        print('    OK T1b : le titre, la référence et la conclusion sont dans '
              'les DEUX formats')

    def test_la_source_est_nommee_dans_les_deux_formats(self):
        """Le succès se dit des deux côtés, pas seulement à l'écran."""
        html, word = _produire([])
        self.assertIn('ActuarIA Intelligence', html)
        self.assertIn('ActuarIA Intelligence', word)
        print('    OK T1c : le marqueur de source est dans les deux formats')

    def test_un_echec_se_voit_dans_les_deux_formats(self):
        """⚠️ SINON ON REMPLACE DEUX COMMENTAIRES DIVERGENTS PAR UN SILENCE.
        Le Word ne nommait sa source qu'en cas de SUCCÈS : un repli y était
        indiscernable d'une narration réussie."""
        appels = []
        html, word = _produire(appels, echouer=True)
        self.assertEqual(len(appels), 1, 'le repli est calculé une seule fois')
        for texte in (html, word):
            self.assertIn('commentaire_agent', texte)   # la source est nommée
            self.assertIn('REPLI AGENT', texte)         # le même texte
            self.assertNotIn('ActuarIA Intelligence', texte)
        print('    OK T1d : un échec est NOMMÉ dans les deux formats, et le '
              'repli y est identique')

    def test_appeles_seuls_les_exports_restent_autonomes(self):
        """L'API publique ne change pas : sans narration fournie, chaque
        export calcule la sienne, comme avant."""
        appels = []
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'cle-de-test'}):
            with patch('anthropic.Anthropic', _client_simule(appels)):
                html = R.export_html(A3, A4, A6, 'DEMO', '31/12/2025', 'T1')
        self.assertEqual(len(appels), 1)
        self.assertIn('Goldburd', html)
        print('    OK T1e : export_html appelé seul calcule sa narration')


class T2_LeContexteDeNarration(unittest.TestCase):
    """T2 — le prompt ordonne « §4 — COMPARAISON DES MODÈLES ML ET SÉLECTION ».

    ⚠️ MESURÉ SUR LE RAPPORT RÉEL PRODUIT AVANT CE LOT : le §4 citait
    1 modèle sur 7, aucun contrôle de sélection, et pas une occurrence de
    « comparaison » hors de son propre titre. `cl4` et `val6` étaient extraits
    puis jetés — `ruff F841` les signalait depuis toujours.
    """

    CLASSEMENT = [
        {'modele': 'GLM Poisson (référence A3)', 'famille': 'GLM',
         'gini_test': 0.1775, 'rmse_test': 0.4504, 'overfit_ratio': 1.000},
        {'modele': 'lightgbm', 'famille': 'Arbres / Boosting',
         'gini_test': 0.1729, 'rmse_test': 0.4579, 'overfit_ratio': 2.757},
        {'modele': 'xgboost_tweedie', 'famille': 'Arbres / Boosting',
         'gini_test': 0.1120, 'rmse_test': 0.4629, 'overfit_ratio': 5.248},
    ]
    CONTROLES = {
        'c1_nb_modeles': {'statut': 'VERT',
                          'message': '7 modèles comparés ≥ 3 → robuste'},
        'c2_ecart_gini': {'statut': 'VERT',
                          'message': 'Écart Gini = 0.0655 ≥ 2%'},
        'c3_coherence': {'statut': 'AMBRE',
                         'message': 'GLM_POISSON rang #1'},
    }

    def _contexte(self, classement=None, controles=None):
        a4 = {'classement': self.CLASSEMENT if classement is None else classement}
        a6 = {'branche': 'auto',
              'validation_selection': (self.CONTROLES if controles is None
                                       else controles)}
        return R._construire_contexte_tarif(A3, a4, a6, 'auto', '31/12/2025')

    def test_les_modeles_compares_entrent_TOUS_dans_le_contexte(self):
        ctx = self._contexte()
        for modele in ('GLM Poisson (référence A3)', 'lightgbm',
                       'xgboost_tweedie'):
            self.assertIn(modele, ctx, modele)
        self.assertIn('CLASSEMENT ML (3 modèle(s) comparé(s))', ctx)
        print('    OK T2 : les 3 modèles comparés sont dans le contexte '
              '(1 sur 7 avant ce lot)')

    def test_les_indicateurs_qui_permettent_de_comparer_y_sont(self):
        """⚠️ C'EST L'ÉCART D'OVERFIT QUI JUSTIFIE LE CHOIX : lightgbm est à
        0,0046 de Gini du GLM, mais à 2,757 de surapprentissage contre 1,000.
        Sans ces chiffres, la « comparaison » n'a rien à dire."""
        ctx = self._contexte()
        for valeur in ('Gini=0.1729', 'overfit=2.757', 'overfit=5.248',
                       'RMSE=0.4504'):
            self.assertIn(valeur, ctx, valeur)
        print('    OK T2b : Gini, RMSE et surapprentissage de chaque modèle')

    def test_les_trois_controles_de_selection_y_sont(self):
        ctx = self._contexte()
        self.assertIn('=== CONTRÔLES DE SÉLECTION ===', ctx)
        for attendu in ('C1 — nombre de modèles comparés : VERT',
                        'C2 — écart de Gini entre modèles : VERT',
                        'C3 — cohérence du modèle retenu : AMBRE'):
            self.assertIn(attendu, ctx, attendu)
        print('    OK T2c : les 3 contrôles de sélection, avec leur statut')

    def test_une_valeur_non_calculee_ne_vaut_pas_zero(self):
        """⚠️ UN GINI À 0,0000 AFFIRMERAIT UN POUVOIR DISCRIMINANT NUL. Sur le
        rapport réel, `score_global` est absent des sept entrées : il doit
        sortir « — », jamais « 0.0000 »."""
        ctx = self._contexte(classement=[{'modele': 'sans_metrique'}])
        self.assertIn('Gini=— | RMSE=— | overfit=— | score=—', ctx)
        self.assertNotIn('0.0000', ctx.split('CLASSEMENT ML')[1].split('===')[0])
        print('    OK T2d : une métrique absente sort « — », pas « 0.0000 »')

    def test_un_classement_vide_SE_DIT(self):
        """L'absence se nomme — elle ne laisse pas une section muette."""
        ctx = self._contexte(classement=[])
        self.assertIn('aucun classement transmis', ctx)
        ctx2 = self._contexte(controles={})
        self.assertIn('non calculé', ctx2)
        print('    OK T2e : un classement vide et un contrôle absent se disent')

    def test_aucun_identifiant_n_est_reintroduit(self):
        """⚠️ CE LOT AJOUTE DES DONNÉES AU CONTEXTE — le chantier C1-C3 vient
        d'établir qu'aucun identifiant n'en sort. Noms d'algorithmes et
        indicateurs, oui ; référence client ou entité, non."""
        motif = re.compile(
            r'entite|entité|ref_client|client_nom|societe|société|'
            r'raison_sociale|siren|siret|numero_police|matricule', re.I)
        fautives = [l for l in self._contexte().split('\n') if motif.search(l)]
        self.assertEqual(fautives, [], '; '.join(fautives))
        print('    OK T2f : aucun motif identifiant dans le contexte enrichi')


class T4_CeQuiNEstPasCalcule(unittest.TestCase):
    """T4 — ne jamais fabriquer un chiffre pour combler un trou.

    ⚠️ RÈGLE DU PROJET, SANS EXCEPTION : une case vide honnête vaut mieux
    qu'un nombre faux ; publier ce qui n'a pas pu être calculé plutôt que de
    le cacher.
    """

    def _html(self, a3=None, a4=None, a6=None):
        with patch.dict(os.environ, {}, clear=False):
            return R.export_html(a3 or {}, a4 or {}, a6 or {},
                                 'DEMO', '31/12/2025', 'T4')

    def test_le_score_vient_du_classement_SCORE_d_A6(self):
        """⚠️ LE SCORE EXISTAIT — LE RAPPORT LISAIT LA MAUVAISE SOURCE. A4
        range les modèles, A6 les SCORE et publie son propre classement. La
        colonne Score était vide sur les SEPT lignes pendant que la section
        « Modèle retenu » affichait 1.0000 : deux vérités sur le même modèle.
        """
        a4 = {'classement': [{'modele': 'GLM', 'gini_test': 0.1775}]}
        a6 = {'classement': [{'modele': 'GLM', 'gini_test': 0.1775,
                              'score_global': 1.0}],
              'modele_production': {'modele': 'GLM', 'score_global': 1.0}}
        html = self._html(a4=a4, a6=a6)
        self.assertIn('1.0000', html)
        # sans A6, on lit A4 — et le score absent sort en tiret, pas en zéro
        html_sans_a6 = self._html(a4=a4)
        self.assertIn('—', html_sans_a6)
        self.assertNotIn('0.0000', html_sans_a6.split('Classement ML')[1][:900])
        print('    OK T4 : le score vient du classement SCORÉ d\'A6')

    def test_une_metrique_absente_ne_vaut_pas_zero(self):
        """⚠️ UN GINI À 0,0000 AFFIRME UN POUVOIR DISCRIMINANT NUL. Le code
        portait déjà un commentaire disant qu'UNE colonne sur quatre avait été
        corrigée ; les trois autres portaient encore le défaut."""
        html = self._html(a3={'metriques': {'poisson': {}}},
                          a6={'modele_production': {'modele': 'GLM'}})
        bloc = html.split('Résultats GLM')[1][:600]
        self.assertNotIn('0.0000', bloc)
        self.assertIn('—', bloc)
        print('    OK T4b : une métrique absente sort « — », jamais « 0.0000 »')

    def test_une_hypothese_non_calculee_NE_DISPARAIT_PLUS(self):
        """⚠️ DOUZE ENDROITS DU DÉPÔT PROMETTENT « H1–H4 » et trois sites
        effaçaient la ligne : le lecteur ne pouvait pas distinguer
        « vérifiée » de « jamais calculée »."""
        a3 = {'hypotheses': {'h1_poisson': {'statut': 'VERT',
                                            'ratio_disp': 1.022}}}
        html = self._html(a3=a3, a6={'modele_production': {}})
        bloc = html.split(R.chapitre(4))[1].split('</table>')[0]
        self.assertIn('NON CALCULÉE', bloc)
        # les quatre hypothèses GLM figurent, calculées ou non
        # ⚠️ T5 les a NOMMÉES : elles s'appelaient « H1 » à « H4 » à côté de
        # « H1 ML » à « H4 ML », soit huit lignes pour quatre numéros.
        for h in ('H1 GLM —', 'H2 GLM —', 'H3 GLM —', 'H4 GLM —'):
            self.assertIn(h, bloc, h)
        print('    OK T4c : les hypothèses non calculées sont NOMMÉES, pas '
              'effacées')

    def test_un_texte_trop_long_est_coupe_SUR_UN_MOT_et_le_dit(self):
        """⚠️ LE RAPPORT COUPAIT EN PLEIN MOT, SANS RIEN DIRE : « le GLM est
        bien spécifié sur toute ». La phrase semblait mal écrite, pas
        tronquée."""
        from core.format_fr import tronque
        long = ('Dispersion homogène entre bandes de risque — le GLM est bien '
                'spécifié sur toute la plage des primes prédites')
        coupe = tronque(long, 80)
        self.assertTrue(coupe.endswith('…'))
        self.assertLessEqual(len(coupe), 81)
        self.assertFalse(coupe[:-1].endswith(' '))
        # la coupure tombe sur une frontière de mot
        self.assertTrue(long.startswith(coupe[:-1]))
        self.assertIn(' ', coupe)
        mot_coupe = coupe[:-1].rsplit(' ', 1)[-1]
        self.assertIn(mot_coupe, long.split())
        print(f'    OK T4d : « …{coupe[-28:]} » — coupé sur un mot, et dit')

    def test_un_texte_court_n_est_pas_touche(self):
        from core.format_fr import tronque
        self.assertEqual(tronque('GLM Poisson adapté', 80), 'GLM Poisson adapté')
        self.assertEqual(tronque(None, 80), '')
        print('    OK T4e : un texte court passe intact')


# ── T5 : un payload complet, pour voir les DEUX formats en entier ───────────
# ⚠️ LES TESTS PRÉCÉDENTS SE CONTENTAIENT D'UN A3 MINIMAL : ils ne rendaient
# ni classement, ni backtesting, ni contrôles de sélection — c'est-à-dire
# précisément les tableaux où les deux formats divergeaient.
A3_COMPLET = {
    'metriques': {
        'poisson': {'gini': 0.1775, 'aic': 10308.0, 'deviance': 8421.5,
                    'pseudo_r2': 0.0412, 'nb_vars_retenues': 9},
        'gamma': {'gini': 0.0912, 'aic': 20114.0, 'deviance': 15012.3,
                  'pseudo_r2': 0.0188, 'nb_vars_retenues': 7},
    },
    'relativites_poisson': {
        'age_conducteur': {'beta': -0.2841, 'relativite': 0.7527,
                           'ic95_low': 0.6902, 'ic95_high': 0.8208,
                           'pvalue': 0.0001, 'significatif': True,
                           'sens': 'allegant'},
    },
    'hypotheses': {
        'h1_poisson': {'statut': 'VERT', 'ratio_disp': 1.022,
                       'message': 'Var/E = 1.02 < 2', 'conseil': 'GLM adapte'},
    },
    'commentaire': 'REPLI AGENT',
}
A4_COMPLET = {'classement': [], 'commentaire': 'REPLI AGENT'}
A6_COMPLET = {
    'branche': 'auto', 'statut_rag': 'VERT',
    'classement': [
        {'modele': 'GLM_POISSON', 'famille': 'GLM', 'gini_test': 0.1775,
         'rmse_test': 0.4504, 'overfit_ratio': 1.0, 'score_global': 1.0},
        {'modele': 'ML_LIGHTGBM', 'famille': 'ML', 'gini_test': 0.1729,
         'rmse_test': 0.4579, 'overfit_ratio': 2.757, 'score_global': 0.6696},
    ],
    'modele_production': {'modele': 'GLM_POISSON', 'famille': 'GLM',
                          'score_global': 1.0, 'gini_test': 0.1775,
                          'overfit_ratio': 1.0, 'interpretabilite': 1.0},
    'validation_selection': {
        'c1_nb_modeles': {'statut': 'VERT', 'message': '7 modeles compares'},
        'c2_ecart_gini': {'statut': 'VERT', 'message': 'Ecart = 0.0655'},
        'c3_coherence': {'statut': 'VERT', 'message': 'Rang 1 coherent'},
    },
    'backtest': {
        'disponible': True, 'ae_ratio': 0.9947, 'interpretation': 'Bon',
        'stabilite_wf': 'Stable', 'n_fenetres': 4,
        'walk_forward': [
            {'annee_test': 2023, 'n_train': 9528, 'n_test': 2472,
             'moy_train': 0.21, 'moy_test': 0.21, 'ae_ratio': 0.9947,
             'statut': 'VERT'},
        ],
    },
    'audit_trail': {'agent': 'A6_COMPARAISON', 'ae_ratio': 0.9947,
                    'stabilite_wf': 'Stable', 'nb_modeles': 7,
                    'gouvernance_ok': True, 'modele_production': 'GLM_POISSON',
                    'timestamp': '2026-08-08T06:34:34.813112'},
}


def _les_deux_formats():
    """Le MÊME payload dans les deux formats, sans réseau."""
    appels = []
    with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'cle-de-test'}):
        with patch('anthropic.Anthropic', _client_simule(appels)):
            rap = R.generer_rapport_tarification(
                A3_COMPLET, A4_COMPLET, A6_COMPLET, 'DEMO', '31/12/2025',
                'T5', ['html', 'word'])
    html = (rap.get('html_bytes') or b'').decode('utf-8', 'replace')
    return html, rap.get('word_bytes') or b''


def _entetes_html(html):
    return {re.sub(r'<[^>]+>', '', c).strip()
            for c in re.findall(r'<th[^>]*>(.*?)</th>', html, re.S)}


def _entetes_word(octets):
    """Les en-têtes du Word : la 1re ligne de chaque tableau du document."""
    from docx import Document
    doc = Document(io.BytesIO(octets))
    return {c.text.strip() for t in doc.tables for c in t.rows[0].cells}


class T5_LeVocabulaire(unittest.TestCase):
    """T5 — un en-tête défini deux fois diverge.

    ⚠️ MESURÉ AVANT CE LOT sur un payload réel : 21 libellés communs aux deux
    formats, 12 propres à l'HTML, 10 propres au Word. Les mêmes colonnes
    portaient « IC 95% bas » d'un côté et « IC bas » de l'autre.
    """

    def test_les_titres_de_colonnes_vivent_a_UN_SEUL_endroit(self):
        """Le motif du chantier : la source est unique, les formats la lisent.

        Un test qui recopierait les libellés attendus recréerait la deuxième
        définition qu'on vient de supprimer — il lit donc la source.
        """
        html, word = _les_deux_formats()
        h, w = _entetes_html(html), _entetes_word(word)
        for cle in ('glm', 'relativites', 'classement', 'hypotheses',
                    'backtest', 'controles', 'audit'):
            for titre in R.titres(cle):
                self.assertIn(titre, h, f'HTML · {cle} · {titre}')
                self.assertIn(titre, w, f'WORD · {cle} · {titre}')
        print(f'    OK T5 : {sum(len(R.titres(c)) for c in R.COLONNES)} '
              f'libellés, une seule définition, lue par les deux formats')

    def test_ce_qui_reste_propre_a_UN_format_est_DECLARE(self):
        """⚠️ UN CHOIX SE DÉCLARE ; CE QUI NE SE DÉCLARE PAS EST UN OUBLI.
        Avant ce lot, six colonnes et un tableau entier manquaient au Word
        sans qu'aucun commentaire du dépôt ne le mentionne."""
        html, word = _les_deux_formats()
        h, w = _entetes_html(html), _entetes_word(word)
        # les deux tableaux propres au Word, page de garde et fiche modèle
        declares_word = set(R.titres('garde')) | set(R.titres('production'))
        self.assertEqual(w - h - declares_word, set())
        # l'étoile décorative, propre à l'HTML
        self.assertEqual(h - w, {'⭐'})
        print(f'    OK T5b : {len(h - w)} propre HTML + '
              f'{len(w - h)} propres Word, tous déclarés')

    def test_les_huit_hypotheses_portent_HUIT_noms(self):
        """⚠️ QUATRE S'APPELAIENT « H1 » À « H4 » ET QUATRE « H1 ML » À
        « H4 ML », sous un titre qui annonçait « H1–H4 »."""
        libelles = [lib for _, lib, _ in R.HYPOTHESES]
        self.assertEqual(len(libelles), 8)
        self.assertEqual(len(set(libelles)), 8)
        for lib in libelles:
            self.assertRegex(lib, r'^H[1-4] (GLM|ML) — ')
        html, _ = _les_deux_formats()
        self.assertNotRegex(html, r'>H[1-4] — ')
        print('    OK T5c : 8 hypothèses, 8 noms, la famille dans chacun')

    def test_les_deux_formats_annoncent_les_MEMES_chapitres(self):
        """⚠️ « §1 — Résultats GLM Poisson / Gamma / Tweedie » en HTML et
        « 1. Résultats GLM — Poisson / Gamma / Tweedie » en Word : 8 titres,
        0 identique."""
        html, word = _les_deux_formats()
        texte_word = _texte_docx(word)
        for n in range(1, len(R.CHAPITRES) + 1):
            titre = R.chapitre(n)
            self.assertIn(titre, html, f'HTML · {titre}')
            self.assertIn(titre, texte_word, f'WORD · {titre}')
        print(f'    OK T5d : {len(R.CHAPITRES)} chapitres, mot pour mot dans '
              f'les deux formats')

    def test_le_rapport_ne_dit_plus_paragraphe_N_comme_la_narration(self):
        """⚠️ « §4 » DÉSIGNAIT DEUX CHOSES : le chapitre « Hypothèses » du
        rapport et, dans le commentaire, la section « COMPARAISON DES MODÈLES »
        que le prompt impose. Un renvoi « voir §4 » n'y voulait rien dire."""
        for titre in R.CHAPITRES:
            self.assertNotIn('§', titre)
        html, _ = _les_deux_formats()
        # les « §N » restants sont ceux de la narration, et d'elle seule
        narration = html.split('class="section-body narration"')[1]
        for m in re.finditer(r'§\s*\d', html):
            self.assertGreaterEqual(
                m.start(), html.index('class="section-body narration"'),
                'un « §N » hors du commentaire actuariel')
        self.assertIn('§1', narration)
        print('    OK T5e : « §N » n\'appartient plus qu\'au commentaire')

    def test_un_modele_porte_UN_nom(self):
        """⚠️ « GLM Poisson (référence A3) » au classement et « GLM_POISSON »
        deux chapitres plus loin. Et la même chaîne produit deux écritures
        selon le passage : « lightgbm » ici, « ML_LIGHTGBM » là."""
        self.assertEqual(R.nom_modele('GLM_POISSON'), 'GLM Poisson')
        self.assertEqual(R.nom_modele('ML_LIGHTGBM'), 'LightGBM')
        self.assertEqual(R.nom_modele('lightgbm'), 'LightGBM')
        self.assertEqual(R.nom_modele('ML_LINEAIRE_REGULARISE'),
                         'Linéaire régularisé')
        # la provenance est une information, pas un nom : elle est conservée
        self.assertEqual(R.nom_modele('GLM Poisson (référence A3)'),
                         'GLM Poisson (référence A3)')
        # ⚠️ UN NOM INCONNU N'EST JAMAIS REMPLACÉ — un nom inventé serait pire
        self.assertEqual(R.nom_modele('MODELE_FUTUR'), 'MODELE_FUTUR')
        self.assertEqual(R.nom_modele(None), '—')
        html, word = _les_deux_formats()
        texte_word = _texte_docx(word)
        for forme in ('GLM_POISSON', 'ML_LIGHTGBM'):
            self.assertNotIn(forme, html, f'HTML · {forme}')
            self.assertNotIn(forme, texte_word, f'WORD · {forme}')
        print('    OK T5f : les identifiants techniques ne sortent plus')

    def test_la_piste_d_audit_se_lit_en_francais(self):
        """⚠️ « Ae Ratio », « Stabilite Wf », « Gouvernance Ok : True » et un
        horodatage à la microseconde — des noms de variables capitalisés."""
        self.assertEqual(R.libelle_audit('ae_ratio'), 'Ratio A/E')
        self.assertEqual(R.valeur_audit(True), 'oui')
        self.assertEqual(R.valeur_audit(False), 'non')
        self.assertEqual(R.valeur_audit('2026-08-08T06:34:34.813112'),
                         '08/08/2026 à 06 h 34')
        # ⚠️ UNE CLÉ INCONNUE RESTE VISIBLE : une piste d'audit amputée n'en
        # serait plus une.
        self.assertEqual(R.libelle_audit('cle_inconnue'), 'Cle inconnue')
        html, word = _les_deux_formats()
        texte_word = _texte_docx(word)
        for brut in ('Ae Ratio', 'Stabilite Wf', 'Nb Modeles',
                     'Gouvernance Ok'):
            self.assertNotIn(brut, html, f'HTML · {brut}')
            self.assertNotIn(brut, texte_word, f'WORD · {brut}')
        self.assertIn('Ratio A/E', html)
        self.assertIn('Ratio A/E', texte_word)
        print('    OK T5g : 14 clés techniques devenues des libellés')

    def test_le_Word_porte_les_colonnes_et_le_tableau_qui_lui_manquaient(self):
        """⚠️ SIX COLONNES ET UN TABLEAU ENTIER. Le fichier qui part chez un
        commissaire n'avait ni la déviance, ni le RMSE, ni l'effectif de test,
        ni les moyennes, ni les trois contrôles qui justifient la sélection."""
        _, word = _les_deux_formats()
        texte = _texte_docx(word)
        for manquant in ('Déviance', 'RMSE test', 'N test', 'Moy train',
                         'Moy test', 'Contrôle sélection'):
            self.assertIn(manquant, texte, manquant)
        for controle in ('C1 — Nombre de modèles', 'C2 — Écart Gini',
                         'C3 — Cohérence'):
            self.assertIn(controle, texte, controle)
        print('    OK T5h : 6 colonnes + 3 contrôles rendus au Word')

    def test_aucun_tableau_du_Word_ne_deborde_de_la_page(self):
        """⚠️ AJOUTER UNE COLONNE PEUT COÛTER LA LISIBILITÉ : la largeur utile
        est de 16,5 cm, marges déduites. Elle se vérifie, elle ne s'espère
        pas."""
        from docx import Document
        from docx.shared import Cm
        _, word = _les_deux_formats()
        doc = Document(io.BytesIO(word))
        for n, t in enumerate(doc.tables, 1):
            largeur = sum((c.width or 0) / Cm(1) for c in t.rows[0].cells)
            self.assertLessEqual(round(largeur, 1), 16.5,
                                 f'tableau {n} : {largeur:.1f} cm')
        print(f'    OK T5i : {len(doc.tables)} tableaux, tous dans 16,5 cm')

    def test_une_hypothese_absente_se_voit_AUSSI_dans_le_Word(self):
        """⚠️ LE WORD LA FAISAIT DISPARAÎTRE EN SILENCE là où l'HTML la publie
        « NON CALCULÉE » depuis T4 : le livrable signé était le plus indulgent
        des deux."""
        _, word = _les_deux_formats()
        texte = _texte_docx(word)
        # A3_COMPLET ne porte que h1_poisson : les sept autres sont absentes
        self.assertIn('NON CALCULÉE', texte)
        for _, libelle, _ in R.HYPOTHESES:
            self.assertIn(libelle, texte, libelle)
        print('    OK T5j : 8 hypothèses nommées dans le Word, calculées ou '
              'non')


if __name__ == '__main__':
    unittest.main(verbosity=2)
