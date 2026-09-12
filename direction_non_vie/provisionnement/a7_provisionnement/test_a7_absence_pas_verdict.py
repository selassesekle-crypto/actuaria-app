# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — UNE ABSENCE NE PRODUIT PAS DE VERDICT FAVORABLE
=============================================================================

 CE FICHIER N'EST PAS UN LOT DE PLUS : C'EST UNE DOCTRINE DEJA ECRITE, DONT
 L'ASSIETTE S'ARRETAIT AVANT LE PROVISIONNEMENT.

 `direction_non_vie/tarification` porte `test_litteral_neutre` (LN-1..LN-6)
 et `test_absence_pas_verdict` (MW-1..MW-7). Les deux scellent la meme chose :
 un littéral neutre ne prend pas la place d'une absence, et une absence ne
 produit pas de verdict. Cote provisionnement, rien ne les relayait — et
 QUATRE constats du 11/09/2026 en sont sortis :

     back-testing sans annee mature .... VERT, score 100,0, ratio 100,0 %
     Barnett-Zehnwirth indisponible .... 'statut': 'VERT'
     agregats S2 non calculables ....... 0 EUR dans le classeur
     percentiles non definis .......... -708 867 EUR dans le Word signe

 CE QU'IL MESURE, ET DANS QUEL ORDRE.

 ⚠️⚠️ LE COMPORTEMENT D'ABORD. Le garde-fou existant
 `T5_Une_Panne_N_Est_Pas_Verte` cherche `'success': False` dans les TROIS
 LIGNES qui precedent un `'statut': 'VERT'` : il a ferme huit branches et la
 NEUVIEME y a survecu, parce qu'elle porte `'success': True` sur la MEME
 ligne — la fonction a abouti, elle a su dire qu'elle ne pouvait pas conclure.
 Un controle qui lit le TEXTE du code sur une fenetre de trois lignes n'est
 pas une doctrine.

 ⚠️ LE TEXTE ENSUITE, ET ELARGI. Le balayage AST attrape le motif de D-F —
 un littéral neutre pose dans la branche `else` d'un test d'ABSENCE — que
 le comportement seul n'atteindrait pas sur une branche ecrite demain.
=============================================================================
"""
import ast
import io
import logging
import pathlib
import unittest
import warnings

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement,
)

#: ⚠️⚠️ ON NE COUPE PAS LES JOURNAUX A L IMPORT. Le correctif recu posait
#: `logging.disable(logging.CRITICAL)` en tete de module ; le depot
#: l INTERDIT et `core/test_journaux_importables.py::F5_LeDepotEntier`
#: echoue dessus. La raison est ecrite dans `test_a7_ibrahim` l.347 : ce
#: motif a deja MASQUE un `logger.error` reel et laisse une regression
#: survivre DEUX lots. La sourdine reste, BORNEE a la duree des tests.
_SOURDINE = None

_ICI = pathlib.Path(__file__).resolve().parent

#: Ce qu'un statut ne peut pas valoir quand rien n'a ete mesure.
_FAVORABLES = ('VERT', 'OK', 'VALIDÉE', 'VALIDEE', 'CONFORME')

#: Les grandeurs dont un littéral neutre se lit comme une bonne nouvelle.
_NEUTRES = (100.0, 100, 0.0, 0)

#: Les noms qui portent un verdict ou une note. Un littéral neutre pose sur
#: l'un d'eux, dans une branche d'ABSENCE, est le motif de D-F.
_PORTEURS = ('statut', 'score', 'ratio', 'note', 'qualite', 'verdict')


def _degeneres():
    """Des triangles ou QUELQUE CHOSE ne peut pas etre mesure — et c'est le
    seul point commun qu'on leur demande."""
    petit = np.array([[100., 180., 220.],
                      [120., 200., np.nan],
                      [130., np.nan, np.nan]])
    # 12 annees, 2 colonnes : AUCUNE annee ne peut etre mature.
    plat = np.zeros((12, 2))
    for i in range(12):
        plat[i, 0] = 1000.0 * (1 + 0.02 * i)
        plat[i, 1] = plat[i, 0] * 1.35
    # Recours massif : le log-normal y est structurellement inapplicable.
    rec = np.zeros((8, 8))
    for i in range(8):
        c = 100000.0 * (1 + 0.03 * i)
        for j in range(8 - i):
            if j:
                c *= 0.90 if j % 3 else 1.10
            rec[i, j] = c
    return (('3x3 non testable', petit),
            ('12x2 aucune annee mature', plat),
            ('8x8 a recours massif', rec))


def _run(C):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return AgentA7Provisionnement(verbose=False).run(
            source=np.asarray(C, dtype=float), mode_declare='cumule',
            n_sim_bootstrap=20, seed=42, generer_graphiques=False,
            generer_word=False, generer_html=True)


def setUpModule():
    """⚠️ LA SOURDINE EST BORNEE, ET POSEE AU NIVEAU DU MODULE.

    Le correctif recu coupait les journaux A L IMPORT.
    `core/test_journaux_importables.py::F5_LeDepotEntier` l interdit pour
    tout le depot, et la raison est ecrite dans `test_a7_ibrahim` l.347 : ce
    motif a deja MASQUE un `logger.error` reel et laisse une regression
    survivre DEUX lots (export Excel retombe a 0 octet).

    ⚠️ POURQUOI `setUpModule` ET NON `setUpClass`. Ce fichier definit deja un
    `setUpClass` ; la DERNIERE definition gagne, la mienne ne tournait donc
    jamais et `tearDownClass` recevait `None` — mesure : 3 erreurs sur 13
    tests. `setUpModule` n a pas ce probleme : unittest l appelle une fois,
    avant toute classe, et `tearDownModule` apres la derniere.
    """
    global _SOURDINE
    _SOURDINE = logging.root.manager.disable
    logging.disable(logging.CRITICAL)


def tearDownModule():
    logging.disable(_SOURDINE)


class T_Aucune_Mesure_Absente_Ne_Prend_Une_Couleur_Favorable(
        unittest.TestCase):
    """⚠️⚠️ LE COMPORTEMENT, SUR TOUS LES SOUS-RESULTATS A LA FOIS."""

    @classmethod
    def setUpClass(cls):
        cls.dossiers = [(nom, _run(C)) for nom, C in _degeneres()]

    def test_aucun_sous_resultat_indisponible_ne_rend_un_statut_favorable(
            self):
        """⚠️ LA GENERALISATION DE D-G, ET ELLE NE CONNAIT AUCUN NOM DE
        MODULE. On balaie TOUT `n3` : si un sous-resultat se declare
        indisponible ou en echec, son statut ne peut pas etre favorable."""
        fautifs = []
        vus = 0
        for nom, r in self.dossiers:
            for cle, bloc in (r.get('n3') or {}).items():
                if not isinstance(bloc, dict):
                    continue
                absent = (bloc.get('disponible') is False
                          or bloc.get('success') is False)
                if not absent:
                    continue
                vus += 1
                if str(bloc.get('statut')) in _FAVORABLES:
                    fautifs.append('%s / n3[%r] : disponible=%r success=%r '
                                   'statut=%r'
                                   % (nom, cle, bloc.get('disponible'),
                                      bloc.get('success'), bloc.get('statut')))
        self.assertGreater(
            vus, 0,
            'aucun sous-resultat indisponible sur trois triangles degeneres : '
            'ce controle ne mesure plus ce qu il croit mesurer')
        self.assertEqual(
            fautifs, [],
            'une mesure qui n a pas eu lieu prend la couleur d une mesure '
            'favorable :\n  ' + '\n  '.join(fautifs))
        print('    OK ABS-1 %d sous-resultats indisponibles, aucun favorable'
              % vus)

    def test_aucun_score_chiffre_ne_cotoie_un_verdict_non_evalue(self):
        """⚠️ LA GENERALISATION DE D-F. Un score de 100 a cote de « NON
        EVALUE » se lit comme une bonne note ; c'est une absence."""
        fautifs = []
        vus = 0
        for nom, r in self.dossiers:
            for cle, bloc in (r.get('n3') or {}).items():
                if not isinstance(bloc, dict):
                    continue
                st = str(bloc.get('statut') or '')
                if 'NON' not in st.upper():
                    continue
                vus += 1
                for k, v in bloc.items():
                    if not any(p in k.lower() for p in ('score', 'ratio')):
                        continue
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        fautifs.append('%s / n3[%r][%r] = %r a cote de %r'
                                       % (nom, cle, k, v, st))
        self.assertGreater(vus, 0, 'aucun statut NON ... : rien n est mesure')
        self.assertEqual(
            fautifs, [],
            'un chiffre accompagne un verdict qui declare n avoir rien '
            'mesure :\n  ' + '\n  '.join(fautifs))
        print('    OK ABS-2 %d verdicts « NON ... », aucun chiffre a cote'
              % vus)

    def test_le_document_signe_ne_publie_aucune_qualite_non_mesuree(self):
        """⚠️ ON LIT LE PRODUIT. Un verrou qui s arrete au dictionnaire
        laisserait la phrase sortir dans le HTML."""
        for nom, r in self.dossiers:
            html = r.get('html') or ''
            bt = (r.get('n3') or {}).get('backtesting') or {}
            if 'NON' not in str(bt.get('statut') or '').upper():
                continue
            with self.subTest(dossier=nom):
                self.assertNotIn(
                    'BONNE', html.upper().replace('NON BONNE', ''),
                    'le document affirme une qualite alors que le '
                    'back-testing declare n avoir rien mesure')
                self.assertNotIn('100/100', html)
        print('    OK ABS-3 aucun document ne publie une qualite non mesuree')


class T_Aucun_Litteral_Neutre_Ne_Remplace_Une_Absence(unittest.TestCase):
    """⚠️ LE TEXTE, ET IL EST ELARGI — pour la branche ecrite demain.

    Le motif de D-F, litteralement :

        score = round(np.mean(xs), 1) if xs else 100.0

    Une valeur mesuree d'un cote, un littéral FAVORABLE de l'autre, et le
    test porte sur une ABSENCE. On le cherche par AST, dans tout A7."""

    #: ⚠️ LE PERIMETRE EST CALCULE, PAS ECRIT. Une liste de fichiers se
    #: perimerait au premier module ajoute.
    @staticmethod
    def _modules():
        for f in sorted(_ICI.rglob('*.py')):
            if f.name.startswith('test_') or f.name == '__init__.py':
                continue
            yield f

    @staticmethod
    def _noms(noeud):
        return {n.id for n in ast.walk(noeud) if isinstance(n, ast.Name)}

    @classmethod
    def _est_absence(cls, test, corps):
        """Un test qui interroge la DISPONIBILITE DE LA DONNEE QU'ON RESUME.

        ⚠️⚠️ MON PREMIER CRITERE ACCUSAIT TROP LARGE, ET LE FILET ME L'A DIT.
        Il tenait tout `ast.Name` employe comme booleen pour un test
        d'absence, et signalait `statut = 'AMBRE' if cal_sig else 'VERT'`
        dans `barnett_zehnwirth_ptf` — ou `cal_sig` est un RESULTAT DE MESURE
        (« une rupture calendaire significative a ete trouvee »), pas une
        disponibilite. Un filet trop etroit laisse passer ; un filet trop
        LARGE accuse, et on finit par le desactiver — ce qui est pire.

        LE DISCRIMINANT EST LE CORPS DE LA TERNAIRE. Le motif de D-F etait :

            score_n1 = round(np.mean(scores_n1), 1) if scores_n1 else 100.0

        la branche calculee LIT le nom teste : le test demande « ai-je de
        quoi calculer ? ». Le VERT de B&Z, lui, ne relit pas `cal_sig` : le
        test y demande « qu'ai-je trouve ? ». Les tests EXPLICITES d'absence
        (`not x`, `x is None`, `== 0`) restent retenus sans cette condition.
        """
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            return True
        if isinstance(test, ast.Compare):
            for op, comp in zip(test.ops, test.comparators):
                if isinstance(op, (ast.Is, ast.IsNot)) and \
                        isinstance(comp, ast.Constant) and comp.value is None:
                    return True
                if isinstance(comp, ast.Constant) and comp.value == 0:
                    return True
            return False
        if isinstance(test, ast.Name):
            return test.id in cls._noms(corps)
        return False

    @staticmethod
    def _est_neutre(noeud):
        if not isinstance(noeud, ast.Constant):
            return False
        v = noeud.value
        if isinstance(v, str):
            return v in _FAVORABLES
        if isinstance(v, bool):
            return False
        return v in _NEUTRES

    def test_aucune_ternaire_ne_pose_un_litteral_favorable_sur_une_absence(
            self):
        fautifs = []
        for f in self._modules():
            try:
                arbre = ast.parse(f.read_text(encoding='utf-8'))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            for n in ast.walk(arbre):
                if not isinstance(n, ast.Assign):
                    continue
                cibles = [t.id for t in n.targets if isinstance(t, ast.Name)]
                cibles += [t.slice.value for t in n.targets
                           if isinstance(t, ast.Subscript)
                           and isinstance(getattr(t, 'slice', None),
                                          ast.Constant)
                           and isinstance(t.slice.value, str)]
                if not any(p in str(c).lower()
                           for c in cibles for p in _PORTEURS):
                    continue
                v = n.value
                if not isinstance(v, ast.IfExp):
                    continue
                if self._est_absence(v.test, v.body) and \
                        self._est_neutre(v.orelse):
                    fautifs.append(
                        '%s:%d  %s = ... if <absence> else %r'
                        % (f.name, n.lineno, cibles[0] if cibles else '?',
                           v.orelse.value))
        self.assertEqual(
            fautifs, [],
            'un littéral favorable est posé là où rien n a été mesuré :\n  '
            + '\n  '.join(fautifs))
        print('    OK ABS-4 aucune ternaire ne pose un littéral favorable '
              'sur une absence')

    def test_le_balayage_TROUVE_le_motif_quand_on_le_plante(self):
        """⚠️⚠️ LA CONTRE-EPREUVE DE L'INSTRUMENT. Un balayage qui ne trouve
        jamais rien passerait au vert sur un module vide. On lui soumet le
        motif exact de D-F, tel qu'il etait ecrit."""
        def _compte(source):
            n_trouve = 0
            for n in ast.walk(ast.parse(source)):
                if isinstance(n, ast.Assign) and isinstance(n.value, ast.IfExp):
                    if self._est_absence(n.value.test, n.value.body) and \
                            self._est_neutre(n.value.orelse):
                        n_trouve += 1
            return n_trouve

        # LE MOTIF DE D-F, tel qu'il etait ecrit.
        self.assertEqual(
            _compte('def f(scores_n1):\n'
                    '    score_n1 = round(sum(scores_n1), 1) if scores_n1 '
                    'else 100.0\n'),
            1, 'le balayage ne reconnait plus le motif de D-F')

        # ⚠️⚠️ ET LA CONTRE-EPREUVE DE L'ASSIETTE, celle que ce filet m'a
        # imposee a lui-meme. Mon premier critere tenait tout `Name` employe
        # comme booleen pour une absence, et accusait cette ligne de
        # `barnett_zehnwirth_ptf` — ou `cal_sig` est un RESULTAT DE MESURE.
        # Un filet qui accuse a tort finit desactive, ce qui est pire que rien.
        self.assertEqual(
            _compte("def g(cal_sig):\n"
                    "    statut = 'AMBRE' if cal_sig else 'VERT'\n"),
            0, 'le balayage accuse un VERT qui est un vrai resultat de mesure')

        # Et les tests EXPLICITES d'absence restent pris, sans condition.
        self.assertEqual(
            _compte('def h(x):\n'
                    '    score = x.moyenne() if x is not None else 100.0\n'),
            1, 'un test explicite `is None` n est plus reconnu')
        print('    OK ABS-5 le balayage reconnaît le motif planté, et ne '
              'frappe pas un vrai verdict')


if __name__ == '__main__':
    unittest.main(verbosity=1)
