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


if __name__ == '__main__':
    unittest.main(verbosity=2)
