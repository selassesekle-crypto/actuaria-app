r"""
==============================================================================
  UNE FIGURE PROMISE AU CATALOGUE ET NON PRODUITE SE DIT SUR LE DOCUMENT
==============================================================================

⚠️⚠️ `FIG-1` -- LE REMEDE POSE ETAIT UN `logger.warning`. Quand une cle du
CATALOGUE manque aux resultats et qu'aucune condition ne le prevoit,
`figures_disponibles` ecrivait une ligne de journal -- que le lecteur du
document signe ne voit jamais -- et `numeroter` refermait la numerotation
sur le trou. Sa docstring le REVENDIQUE meme : << une figure absente ne
laisse donc aucun trou : la suivante prend son numero >>.

Mesure du 13/09/2026, meme harnais, catalogue de 15 figures dont 3
conditionnelles :

    cas                                    figures   numeros   le doc le dit
    A -- catalogue complet                    15      1..15     sans objet
    B -- sans une NON conditionnelle          14      1..14     **NON**
    C -- sans une CONDITIONNELLE              14      1..14     sans objet

*B et C etaient INDISCERNABLES : une absence prevue et un defaut se
lisaient pareil.* Et le module savait deja declarer une non-production
sur la surface signee -- il le fait pour les HYPOTHESES
(<< Hypothese non produite par la chaine >>, deux formats), pas pour les
figures.

⚠️ CE QUI A ETE FAIT : un bloc publie dans les DEUX formats, alimente par
UNE SEULE source (`figures_absentes`) -- deux rendus seraient deux
verites possibles pour le meme fait. L'ensemble se DERIVE du catalogue et
de `FIGURES_CONDITIONNELLES` ; aucune liste ecrite a la main, qui
n'attesterait que ce qu'on a pense a y mettre.

⚠️ ET L'ABSENCE PREVUE RESTE MUETTE, c'est le second sens du sceau : une
figure conditionnelle non produite ne doit RIEN faire apparaitre, sinon
le bloc devient un avertissement permanent, donc un avertissement qu'on
cesse de lire.
==============================================================================
"""
from __future__ import annotations

import ast
import io
import logging
import os
import pathlib
import sys
import types
import unittest
import zipfile

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from direction_non_vie.tarification.services import rapport_modeles_tarif as RM

_SOURCE = (_RACINE / 'direction_non_vie' / 'tarification' / 'services'
           / 'rapport_modeles_tarif.py').read_bytes().decode('utf-8')

_MODELE = {'modele': 'GLM_POISSON', 'famille': 'GLM', 'gini_test': 0.18,
           'gini_train': 0.19, 'overfit_ratio': 1.05, 'score_global': 0.72,
           'rmse_test': 0.31, 'interpretabilite': 1.0, 'rang': 1}


def _figure():
    """Un objet de figure minimal : le catalogue ne teste que `is None`.

    ⚠️ RENDU PAR UNE FABRIQUE plutot que par une classe : `to_html` n'est
    appele que par DUCK TYPING depuis le service, jamais nomme ici -- une
    methode de classe serait declaree morte par l'analyse statique, et la
    retirer casserait le rendu."""
    return types.SimpleNamespace(to_html=lambda **k: '<div>figure</div>')


def _resultats(sans=()):
    """Les quatre resultats, catalogue COMPLET moins `sans`.

    ⚠️ L'assiette se DERIVE de `SOURCES_FIGURES` : une figure ajoutee au
    catalogue entre automatiquement dans ce controle."""
    res = {}
    for a in ('a3', 'a4', 'a5', 'a6'):
        res[a] = {'success': True, 'branche': 'auto', 'statut_rag': 'VERT',
                  'audit_id': 'FIG1', 'classement': [_MODELE],
                  'modele_production': _MODELE,
                  'backtest': {'disponible': False},
                  'graphiques': {}, 'graphiques_validation': {},
                  'rapport': {}, 'audit_trail': {}, 'commentaire': '',
                  'controle_effet': {'execute': True, 'motifs': {}}}
    for cle, (agent, dico) in RM.SOURCES_FIGURES.items():
        if cle in sans:
            continue
        res[agent][dico][cle] = _figure()
    return res


def _html(res):
    #: ⚠️ APPEL PAR MOT-CLE, JAMAIS POSITIONNEL. `export_html` prend
    #: `result_a3` en PREMIER : passer le resultat d'A6 en position le
    #: ferait atterrir dans `result_a3`, et AUCUN bloc issu d'A6
    #: n'apparaitrait -- un faux negatif silencieux. *Une sonde du 3e audit
    #: s'y est prise ainsi et a conclu a tort qu'un bloc manquait.*
    return RM.export_html(result_a3=res['a3'], result_a4=res['a4'],
                          result_a5=res['a5'], result_a6=res['a6'])


def _word_texte(res):
    octets = RM.export_word(result_a3=res['a3'], result_a4=res['a4'],
                            result_a5=res['a5'], result_a6=res['a6'])
    z = zipfile.ZipFile(io.BytesIO(octets))
    return '\n'.join(z.read(n).decode('utf-8', 'replace')
                     for n in z.namelist() if n.endswith('.xml'))


def _une_non_conditionnelle():
    for c in RM.SOURCES_FIGURES:
        if c not in RM.FIGURES_CONDITIONNELLES:
            return c
    raise AssertionError('aucune figure NON conditionnelle au catalogue : '
                         "l'assiette de ce controle est vide")


def _une_conditionnelle():
    for c in RM.SOURCES_FIGURES:
        if c in RM.FIGURES_CONDITIONNELLES:
            return c
    raise AssertionError('aucune figure conditionnelle : la distinction que '
                         'ce controle surveille a disparu')


class TestUneFigureAttendueAbsenteSeDit(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_FA1_SCEAU_une_figure_NON_conditionnelle_absente_se_dit_en_HTML(
            self):
        """⚠️⚠️ LE SCEAU. Le document signe doit porter l'absence, pas le
        journal. *Ce qui n'est que dans un champ technique n'existe pas pour
        l'actuaire qui relit le dossier plus tard.*"""
        cle = _une_non_conditionnelle()
        html = _html(_resultats((cle,)))
        self.assertIn(
            RM.TITRE_FIGURES_ABSENTES, html,
            f"la figure `{cle}` manque au document et rien ne le dit : "
            f"elle disparait en silence, la numerotation se referme dessus")
        self.assertIn(
            RM.TITRES_FIGURES.get(cle, cle), html,
            f'le bloc ne NOMME pas la figure absente `{cle}`')
        print(f"    FA-1 SCEAU HTML : `{cle}` absente -> le document le dit")

    def test_FA2_SCEAU_le_meme_fait_atteint_le_format_WORD(self):
        """⚠️⚠️ LES DEUX FORMATS, MEME SOURCE. N'en poser qu'un laisserait la
        moitie du livrable signe muette -- et deux sources seraient deux
        verites possibles pour le meme fait."""
        cle = _une_non_conditionnelle()
        texte = _word_texte(_resultats((cle,)))
        self.assertIn(
            RM.TITRE_FIGURES_ABSENTES, texte,
            'le .docx ne porte pas le bloc des figures absentes : la moitie '
            'du livrable signe reste muette')
        print(f"    FA-2 SCEAU Word : `{cle}` absente -> le .docx le dit")

    def test_FA3_SCEAU_une_absence_PREVUE_reste_muette(self):
        """⚠️⚠️ LE SECOND SENS, ET C'EST LUI QUI DONNE SON SENS AU PREMIER.
        Une figure declaree dans `FIGURES_CONDITIONNELLES` peut legitimement
        manquer. Si elle declenchait le bloc, l'avertissement deviendrait
        permanent -- et un avertissement permanent cesse d'etre lu."""
        cle = _une_conditionnelle()
        html = _html(_resultats((cle,)))
        self.assertNotIn(
            RM.TITRE_FIGURES_ABSENTES, html,
            f"`{cle}` est declaree CONDITIONNELLE et son absence declenche "
            f"quand meme le bloc : une absence prevue est signalee comme un "
            f"defaut")
        #: ⚠️ ET LA DISTINCTION EST BIEN CELLE QU'ON CROIT : le cas voisin,
        #: lui, parle. Sans cette moitie, le controle passerait aussi sur un
        #: bloc qui ne s'affiche JAMAIS.
        autre = _html(_resultats((_une_non_conditionnelle(),)))
        self.assertIn(RM.TITRE_FIGURES_ABSENTES, autre,
                      'le bloc ne s affiche dans AUCUN des deux cas : le '
                      'controle atteste sur un mecanisme mort')
        print(f"    FA-3 SCEAU : `{cle}` conditionnelle -> muette ; le cas "
              f"voisin parle")

    def test_FA4_CONTRE_EPREUVE_un_catalogue_COMPLET_ne_dit_rien(self):
        """⚠️ CE QUE CE LOT NE DOIT SURTOUT PAS DEPLACER. Sur le cas nominal
        -- toutes les figures produites -- le document ne doit pas gagner une
        ligne."""
        res = _resultats(())
        self.assertEqual(
            RM.figures_absentes(res['a3'], res['a4'], res['a6'],
                                result_a5=res['a5']), (),
            'des figures sont declarees absentes alors que le catalogue est '
            'complet')
        html = _html(res)
        self.assertNotIn(RM.TITRE_FIGURES_ABSENTES, html)
        self.assertNotIn(RM.TITRE_FIGURES_ABSENTES, _word_texte(res))
        self.assertEqual(RM._bloc_figures_html(()), '',
                         'le bloc rend quelque chose sur un tuple vide')
        print('    FA-4 contre-epreuve : catalogue complet -> 0 mention dans '
              'les deux formats')

    def test_FA5_l_ensemble_se_DERIVE_et_son_ordre_est_STABLE(self):
        """⚠️⚠️ UNE ASSIETTE ECRITE A LA MAIN ATTESTE CE QU'ON A PENSE A Y
        METTRE. `figures_absentes` doit lire le CATALOGUE et
        `FIGURES_CONDITIONNELLES`, jamais une liste posee a cote -- sinon une
        figure ajoutee demain sortirait du controle sans que rien ne rougisse.

        ⚠️ ET L'ORDRE DOIT ETRE STABLE : un ensemble non ordonne ferait varier
        le document d'une execution a l'autre, et le gel rougirait sur du
        bruit."""
        f = next(n for n in ast.walk(ast.parse(_SOURCE))
                 if isinstance(n, ast.FunctionDef)
                 and n.name == 'figures_absentes')
        corps = ast.unparse(f)
        for nom in ('SOURCES_FIGURES', 'FIGURES_CONDITIONNELLES'):
            self.assertIn(
                nom, corps,
                f'`figures_absentes` ne lit pas `{nom}` : son assiette est '
                f'posee a cote du catalogue')
        #: une collection litterale de chaines serait une liste a la main ;
        #: les tuples de deballage n'en sont pas.
        mains = [ast.unparse(n) for n in ast.walk(f)
                 if isinstance(n, (ast.List, ast.Set))
                 and any(isinstance(e, ast.Constant) and isinstance(e.value,
                                                                    str)
                         for e in n.elts)]
        self.assertEqual(mains, [],
                         f'une liste de noms ecrite a la main : {mains}')
        res = _resultats((_une_non_conditionnelle(),))
        deux = [RM.figures_absentes(res['a3'], res['a4'], res['a6'],
                                    result_a5=res['a5']) for _ in range(2)]
        self.assertEqual(deux[0], deux[1],
                         'deux executions rendent un ordre different')
        self.assertIsInstance(deux[0], tuple,
                              "l'ensemble n'est pas ordonne : le document "
                              "varierait d'une execution a l'autre")
        print(f"    FA-5 : assiette derivee du catalogue "
              f"({len(RM.SOURCES_FIGURES)} figures dont "
              f"{len(RM.FIGURES_CONDITIONNELLES)} conditionnelles), ordre "
              f"stable")


    def test_FA6_SCEAU_un_agent_NON_FOURNI_ne_compte_pas_pour_absent(self):
        """⚠️⚠️ LE SCEAU DE LA SEULE DEVIATION DE CE LOT, ET ELLE A ETE
        MESUREE TROIS FOIS AVANT D'ETRE POSEE. Un document qui ne recoit pas
        le resultat d'un agent ne peut pas reprocher a la chaine de n'avoir
        pas produit les figures de cet agent.

        Mesure du 13/09/2026 : applique sans cette garde, le bloc publiait
        SEPT figures sur `a4 Word` -- dont SIX ont pour source A6, qui
        n'avait pas encore tourne quand A4 ecrit son document. *Publier
        << attendue et non produite >> pour une figure qu'aucune chaine ne
        pouvait produire la, c'est une instruction erronee sur un document
        signe.* Apres la garde : UNE seule, celle d'A4, qui manque bien.

        ⚠️ Et la garde ETEND : sur le rapport complet, ou les quatre
        resultats sont fournis, elle ne change rien -- `FA-1` le prouve."""
        cle = _une_non_conditionnelle()
        agent = RM.SOURCES_FIGURES[cle][0]
        complet = _resultats(())
        #: on retire ENTIEREMENT le resultat de l'agent qui porte la figure
        sans_agent = {a: (None if a == agent else r)
                      for a, r in complet.items()}
        absentes = RM.figures_absentes(
            sans_agent['a3'], sans_agent['a4'], sans_agent['a6'],
            result_a5=sans_agent['a5'])
        self.assertNotIn(
            cle, absentes,
            f"`{cle}` est reprochee a la chaine alors que le resultat de son "
            f"agent `{agent}` n'a pas ete FOURNI : le document ne couvre pas "
            f"cet agent, ce n'est pas une defaillance. Signalees : {absentes}")
        #: ⚠️ ET LE SECOND SENS : l'agent FOURNI mais sans sa figure reste
        #: signale -- sinon la garde aurait ferme le constat au lieu du bruit.
        ampute = dict(complet)
        ampute[agent] = {**complet[agent],
                         RM.SOURCES_FIGURES[cle][1]: {
                             k: v for k, v
                             in complet[agent][RM.SOURCES_FIGURES[cle][1]
                                               ].items() if k != cle}}
        absentes2 = RM.figures_absentes(
            ampute['a3'], ampute['a4'], ampute['a6'],
            result_a5=ampute['a5'])
        self.assertIn(
            cle, absentes2,
            f"`{cle}` manque alors que son agent `{agent}` EST fourni, et "
            f"elle n'est pas signalee : la garde a ferme le constat")
        print(f"    FA-6 SCEAU : `{agent}` non fourni -> `{cle}` non "
              f"reprochee ; `{agent}` fourni sans elle -> reprochee")


if __name__ == '__main__':
    unittest.main(verbosity=2)
