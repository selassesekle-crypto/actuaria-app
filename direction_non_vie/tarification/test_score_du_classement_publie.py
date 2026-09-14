r"""
==============================================================================
  LE SCORE DU CLASSEMENT ATTEINT LE RAPPORT QUI CIRCULE
==============================================================================

⚠️⚠️ `RET-D2` -- LA COLONNE << SCORE >> ETAIT VIDE SUR SEPT LIGNES SUR
SEPT, DANS LES TROIS FORMATS DU RAPPORT D'EQUIPE. Ses trois sites
lisaient `r4.get('classement')`, et A4 ne produit JAMAIS `score_global`.

Releve AST du 14/09/2026 sur `a4_ml/agent.py` (4 132 lignes) : la cle y
est **posee 0 fois, lue 0 fois, absente du texte**. Les trois dicts
d'entree de son classement portent dix cles -- `modele`, `famille`,
`gini_test`, `gini_train`, `overfit_ratio`, `overfit_ic`, `rmse_test`,
`mae_test`, `overfit_alerte`, `recommandation` -- et aucune n'est
celle-la. La grille multicriteres est calculee par A6, qui la pose a
`a6_comparaison/agent.py:1767`, seul site du depot.

Le jumeau `rapport_modeles_tarif` avait corrige exactement cela a ses
trois sites, avec sa mesure inscrite dans le code : *<< la colonne Score
etait vide sur les SEPT lignes >>*. Le correctif n'avait pas atteint CE
fichier -- **et c'est le rapport d'EQUIPE qui circule.**

⚠️⚠️ ET LE DOCUMENT SE CONTREDISAIT. Mesure du 14/09 sur le Word
reellement produit : son §5 publie << Score global : 0.8741 >>, venu
d'A6, pendant que son tableau de classement affiche << - >> sur la ligne
du MEME modele `xgboost`. *Deux verites sur le meme modele, dans le meme
document signe.* C'est `RS-3` qui tient ce point, et l'auditeur ne
l'avait pas releve sur ce fichier-ci.

Mesure du 14/09, memes donnees, les trois formats produits :

    Excel   7 lignes,  7 sans score   ->   7 lignes, 0 sans score
    HTML    7 lignes,  7 sans score   ->   7 lignes, 0 sans score
    Word    7 lignes,  7 sans score   ->   7 lignes, 0 sans score

⚠️ LE REPLI SUR A4 EST INTACT, et `RS-2` le tient : sans A6, les trois
formats sont IDENTIQUES a ce qu'ils etaient.

⚠️⚠️ L'HORODATAGE SE NEUTRALISE AVANT TOUTE COMPARAISON. Mon premier
essai de contre-epreuve avait enjambe un changement de MINUTE : deux
documents identiques hachaient different, et j'ai lu un ecart de
comportement la ou il n'y avait qu'une horloge. `neutraliser` existe
dans le depot pour cela.

⚠️ LAISSE OUVERT ET NOMME : le titre de la section Excel dit encore
<< CLASSEMENT (A4) >> alors que la colonne Score porte la grille d'A6.
Le jumeau porte la meme imprecision et le correctif recu ne la traite
pas : on ne devie pas d'un correctif d'auditeur sans avoir mesure trois
fois qu'il a tort, et cette mesure n'est pas faite.
==============================================================================
"""
from __future__ import annotations

import ast
import hashlib
import io
import logging
import os
import pathlib
import re
import sys
import unittest
import warnings
import zipfile

_RACINE = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from direction_non_vie.tarification.services import rapport_equipe_tarif as RE
from direction_non_vie.tarification.services.gel_livrables import neutraliser

_SOURCE = (_RACINE / 'direction_non_vie' / 'tarification' / 'services'
           / 'rapport_equipe_tarif.py')

#: ⚠️ Le tableau `<w:t>` se lit avec une frontiere de nom de balise : le
#: motif `<w:t[^>]*>` attrape AUSSI `<w:tcW .../>` et rend des cellules
#: pleines de XML. Mesure : 3 tableaux trouves, 0 en-tete lisible.
_RE_WT = re.compile(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>', re.DOTALL)
_ENTETE = ['Modèle', 'Gini', 'Score', 'Overfit']
_VIDES = ('', 'N/A', '—', '-', 'None', 'nan')

_NOMS = ['xgboost', 'lightgbm', 'random_forest', 'gradient_boosting',
         'extra_trees', 'catboost', 'glm_poisson']
_GINI = [0.9062, 0.8711, 0.8455, 0.8390, 0.8102, 0.7988, 0.7411]
_SCORE = [0.8741, 0.8502, 0.8233, 0.8190, 0.7902, 0.7788, 0.7211]
#: le classement tel qu'A4 le produit : dix cles, pas de `score_global`
_CL_A4 = [{'modele': n, 'famille': 'ml', 'gini_test': g,
           'gini_train': g + 0.02, 'overfit_ratio': 1.11,
           'overfit_ic': [1.0, 1.2], 'rmse_test': 42.0, 'mae_test': 31.0,
           'overfit_alerte': False, 'recommandation': 'retenu'}
          for n, g in zip(_NOMS, _GINI)]
_CL_A6 = [dict(e, score_global=s) for e, s in zip(_CL_A4, _SCORE)]


def _jeu(avec_a6: bool) -> dict:
    r = {'a1': {'success': True, 'statut_rag': 'VERT'},
         'a2': {'success': True, 'statut_rag': 'VERT'},
         'a3': {'success': True, 'statut_rag': 'VERT', 'metriques': {}},
         'a4': {'success': True, 'statut_rag': 'VERT', 'classement': _CL_A4,
                'metriques': {}, 'meilleur_modele': 'xgboost'}}
    if avec_a6:
        r['a6'] = {'success': True, 'statut_rag': 'VERT',
                   'classement': _CL_A6,
                   'modele_production': {'nom': 'xgboost',
                                         'score_global': _SCORE[0]}}
    return r


def _colonne_score_excel(octets) -> list:
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(octets))
    vus = []
    for ws in wb.worksheets:
        for lg in range(1, ws.max_row + 1):
            if [ws.cell(lg, c).value for c in range(1, 5)] != _ENTETE:
                continue
            for k in range(lg + 1, min(lg + 10, ws.max_row + 1)):
                #: ⚠️ UNE LIGNE DE MODELE REMPLIT SES QUATRE CELLULES. La
                #: note de lecture, posee sous la table, n'en remplit que
                #: deux -- et une premiere version de cette sonde la
                #: comptait comme un huitieme modele. *Le defaut etait dans
                #: l'instrument, pas dans le document.*
                if (ws.cell(k, 1).value in (None, '')
                        or ws.cell(k, 4).value in (None, '')):
                    break
                vus.append((ws.cell(k, 1).value, str(ws.cell(k, 3).value)))
    return vus


def _cellules_word(tr) -> list:
    return [''.join(_RE_WT.findall(tc))
            for tc in re.findall(r'<w:tc>.*?</w:tc>', tr, re.DOTALL)]


def _xml_word(octets) -> str:
    with zipfile.ZipFile(io.BytesIO(octets)) as z:
        return z.read('word/document.xml').decode('utf-8', 'replace')


def _colonne_score_word(xml) -> list:
    for tbl in re.findall(r'<w:tbl>.*?</w:tbl>', xml, re.DOTALL):
        lignes = re.findall(r'<w:tr[ >].*?</w:tr>', tbl, re.DOTALL)
        if lignes and _cellules_word(lignes[0])[:4] == _ENTETE:
            return [(_cellules_word(t)[0], _cellules_word(t)[2])
                    for t in lignes[1:] if len(_cellules_word(t)) >= 3]
    return []


def _colonne_score_html(txt) -> list:
    """⚠️ L'ANCRE EST L'EN-TETE ENTIER, JAMAIS UN SEUL LIBELLE. Une
    premiere version cherchait la chaine `Modele ML` ; renommer cette
    colonne -- ce que ce lot fait -- rendait 0 ligne, donc un faux
    rouge. *Une sonde ancree sur un mot meurt quand le mot change.*"""
    vus = []
    for tbl in re.findall(r'<table[^>]*>(.*?)</table>', txt, re.DOTALL):
        lignes = re.findall(r'<tr>(.*?)</tr>', tbl, re.DOTALL)
        if not lignes:
            continue

        def texte(cellule):
            return re.sub(r'<[^>]+>', '', cellule).strip()
        entete = [texte(c) for c in
                  re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', lignes[0],
                             re.DOTALL)]
        if entete[:4] != _ENTETE:
            continue
        for ligne in lignes[1:]:
            tds = [texte(c) for c in
                   re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', ligne,
                              re.DOTALL)]
            if len(tds) >= 4:
                vus.append((tds[0], tds[2]))
    return vus


def _produire(avec_a6: bool) -> dict:
    r = _jeu(avec_a6)
    a = {'branche': 'auto', 'arrete': '2026-09-14', 'audit_id': 'RETD2'}
    x = RE.export_excel_equipe(r, **a)
    h = RE.export_html_equipe(r, **a)
    w = RE.export_word_equipe(r, **a)
    if isinstance(h, bytes):
        h = h.decode('utf-8', 'replace')
    xml = _xml_word(w)
    return {'excel': _colonne_score_excel(x),
            'html': _colonne_score_html(h),
            'word': _colonne_score_word(xml),
            'html_texte': h, 'word_xml': xml,
            'html_sha': hashlib.sha256(
                neutraliser(h).encode('utf-8')).hexdigest(),
            'word_sha': hashlib.sha256(
                neutraliser(xml).encode('utf-8')).hexdigest()}


class TestScoreDuClassementPublie(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._racine = logging.getLogger()
        cls._niveau = cls._racine.level
        cls._racine.setLevel(logging.CRITICAL)
        warnings.filterwarnings('ignore')
        cls.avec = _produire(True)
        cls.sans = _produire(False)

    @classmethod
    def tearDownClass(cls):
        cls._racine.setLevel(cls._niveau)

    # ── RS-1 ─────────────────────────────────────────────────────────────
    def test_RS1_la_colonne_Score_porte_les_scores_aux_TROIS_formats(self):
        """⚠️ LES TROIS, ET PAS UN DE MOINS : ce fichier ecrit six fois
        << corriger un seul des deux formats ? >>, et le PDF avait ete le
        troisieme oublie du jumeau."""
        vus = {}
        for fmt in ('excel', 'html', 'word'):
            lignes = self.avec[fmt]
            self.assertEqual(
                len(lignes), 7,
                f"le format {fmt} ne publie pas les 7 lignes du classement "
                f"mais {len(lignes)} : ce controle ne mesure plus ce qu'il "
                f"annonce")
            vides = [m for m, s in lignes if s in _VIDES]
            vus[fmt] = len(vides)
        self.assertEqual(
            vus, {'excel': 0, 'html': 0, 'word': 0},
            f"la colonne Score reste vide : {vus} ligne(s) sans score par "
            f"format. Le rapport qui CIRCULE publie une colonne vide sur un "
            f"classement que A6 a score.")
        print(f"    RS-1 SCEAU : 7 lignes x 3 formats, "
              f"0 sans score ({self.avec['excel'][0]})")

    # ── RS-2 ─────────────────────────────────────────────────────────────
    def test_RS2_SANS_A6_les_trois_formats_ne_bougent_pas(self):
        """La contre-epreuve, portee dans le depot. ⚠️ L'horodatage
        d'impression est neutralise : sans cela, deux documents identiques
        produits a une minute d'intervalle hachent different -- mesure faite,
        et elle m'avait fait lire un faux ecart."""
        lignes = self.sans['excel']
        self.assertEqual(
            len(lignes), 7,
            "sans A6, le classement d'A4 ne remplit plus la table : le repli "
            "est casse")
        vides = sum(1 for _, s in lignes if s in _VIDES)
        self.assertEqual(
            vides, 7,
            f"sans A6, {7 - vides} ligne(s) portent un score : d'ou "
            f"viendrait-il ? A4 n'en produit aucun.")
        #: l'instrument doit etre stable : on rejoue et on compare a soi
        rejoue = _produire(False)
        self.assertEqual(
            (rejoue['html_sha'], rejoue['word_sha']),
            (self.sans['html_sha'], self.sans['word_sha']),
            "le document n'est pas reproductible d'un lancement a l'autre : "
            "cette contre-epreuve ne prouve rien tant que c'est le cas")
        print(f"    RS-2 SCEAU : sans A6, 7/7 sans score, documents "
              f"reproductibles (html {self.sans['html_sha'][:12]})")

    # ── RS-3 ─────────────────────────────────────────────────────────────
    def test_RS3_le_paragraphe_5_et_le_TABLEAU_disent_la_meme_chose(self):
        """⚠️⚠️ LA CONTRADICTION INTERNE, ET C'EST ELLE LE PIRE. Le §5
        publiait << Score global : 0.8741 >> pendant que le tableau affichait
        << - >> sur la ligne du MEME modele. Un lecteur qui rapproche les deux
        sections d'un document signe ne peut pas trancher laquelle ment."""
        cible = f"{_SCORE[0]:.4f}"
        textes = ' | '.join(_RE_WT.findall(self.avec['word_xml']))
        #: ⚠️⚠️ LE §5 SE CHERCHE PAR SA PHRASE, PAS PAR LE NOMBRE SEUL. Un
        #: plant qui retirait le score du §5 a laisse ce controle VERT : le
        #: nombre vivait aussi dans la TABLE, que le correctif venait de
        #: remplir. *Mon contrôle attestait la presence du chiffre sans
        #: surveiller la section qu'il pretend surveiller.* Mesure du
        #: 14/09/2026, plant D : 0 rouge au lieu de 1.
        phrase_p5 = f"Score global : {cible}"
        self.assertIn(
            phrase_p5, textes,
            f"le §5 du Word ne publie plus la phrase `{phrase_p5}` : ce "
            f"controle ne mesure plus la contradiction qu'il annonce. "
            f"(le nombre seul peut venir de la TABLE -- ce n'est pas la "
            f"meme section.)")
        ligne = [s for m, s in self.avec['word'] if m == _NOMS[0]]
        self.assertTrue(ligne, f"la ligne `{_NOMS[0]}` a disparu du tableau")
        self.assertNotIn(
            ligne[0], _VIDES,
            f"le §5 du Word publie `{cible}` pour `{_NOMS[0]}` et son tableau "
            f"affiche `{ligne[0]}` sur la ligne du MEME modele : deux verites "
            f"sur le meme modele, dans le meme document signe.")
        self.assertEqual(
            float(ligne[0]), _SCORE[0],
            f"le tableau publie {ligne[0]} et le §5 publie {cible} pour "
            f"`{_NOMS[0]}` : le document se contredit toujours.")
        print(f"    RS-3 SCEAU : §5 et tableau disent {cible} du meme modele")

    # ── RS-4 ─────────────────────────────────────────────────────────────
    def test_RS4_AUCUN_des_trois_sites_ne_lit_A4_SEUL(self):
        """⚠️⚠️ LE RELEVE EST PAR AST ET IL PORTE SUR LA FORME. Trois sites
        se ressemblent ; un lot qui en ajoute un quatrieme recopierait le
        plus proche. On interdit la forme, pas un numero de ligne."""
        arbre = ast.parse(_SOURCE.read_bytes().decode('utf-8'))
        sites, fautifs = [], []
        for n in ast.walk(arbre):
            if not isinstance(n, ast.Assign):
                continue
            noms = [c.id for c in n.targets if isinstance(c, ast.Name)]
            if 'cl4' not in noms:
                continue
            source = ast.unparse(n.value)
            sites.append((n.lineno, source[:70]))
            if 'r6' not in source:
                fautifs.append((n.lineno, source[:70]))
        self.assertEqual(
            len(sites), 3,
            f"ce fichier ne porte plus trois sites de classement mais "
            f"{len(sites)} : {sites}. L'assiette de ce controle a change.")
        self.assertEqual(
            fautifs, [],
            f"{len(fautifs)} site(s) lisent le classement d'A4 SANS passer "
            f"par A6 d'abord : {fautifs}. A4 ne pose jamais `score_global`.")
        print(f"    RS-4 SCEAU : {len(sites)} site(s), {len(sites)} lisent "
              f"A6 d'abord, {len(fautifs)} fautif")

    # ── RS-5 ─────────────────────────────────────────────────────────────
    def test_RS5_les_DEUX_JUMEAUX_lisent_la_meme_source(self):
        """⚠️ L'ASYMETRIE ENTRE JUMEAUX est le revelateur le moins cher, et
        c'est elle qui a livre ce constat. On la scelle dans les deux sens :
        le jour ou l'un des deux repart sur A4 seul, ce controle mord."""
        jumeau = (_RACINE / 'direction_non_vie' / 'tarification' / 'services'
                  / 'rapport_modeles_tarif.py')
        compte = {}
        for chemin in (_SOURCE, jumeau):
            arbre = ast.parse(chemin.read_bytes().decode('utf-8'))
            n_a6 = 0
            n_tot = 0
            for n in ast.walk(arbre):
                if isinstance(n, ast.Assign) and any(
                        isinstance(c, ast.Name) and c.id == 'cl4'
                        for c in n.targets):
                    n_tot += 1
                    n_a6 += ('result_a6' in ast.unparse(n.value)
                             or 'r6' in ast.unparse(n.value))
            compte[chemin.name] = (n_a6, n_tot)
        ecarts = {k: v for k, v in compte.items() if v[0] != v[1]}
        self.assertEqual(
            ecarts, {},
            f"les deux fabriques ne lisent plus la meme source : {compte}. "
            f"Une asymetrie entre jumeaux est exactement ce qui a laisse la "
            f"colonne Score vide pendant un round entier.")
        print(f"    RS-5 SCEAU : jumeaux alignes -- {compte}")


    # ── RS-6 ─────────────────────────────────────────────────────────────
    def test_RS6_le_TITRE_dit_vrai_et_la_NOTE_atteint_les_3_formats(self):
        """⚠️⚠️ LE TEXTE QUI ACCOMPAGNE UN COMPORTEMENT SE RELIT QUAND IL
        CHANGE. La section s'intitulait << MACHINE LEARNING - CLASSEMENT
        (A4) >> et son en-tete HTML << Modele ML >> ; la table porte
        desormais le classement d'A6, ou figurent -- mesure du 14/09 sur le
        jeu reel du gel -- `GLM_POISSON` et `DL_CANN`. *Un GLM et un reseau
        de neurones sous un titre qui promettait du ML d'A4.*

        ⚠️ ET L'ORDRE N'EST PAS CELUI DU GINI. `NOTE_CLASSEMENT` le dit, et
        elle vient de sa SOURCE UNIQUE : la recopier ici creerait la seconde
        redaction qui finit par diverger."""
        from openpyxl import load_workbook

        from direction_non_vie.tarification.services.rapport_modeles_tarif import (
            NOTE_CLASSEMENT,
        )
        r = _jeu(True)
        a = {'branche': 'auto', 'arrete': '2026-09-14', 'audit_id': 'RETD2'}
        x = RE.export_excel_equipe(r, **a)
        h = RE.export_html_equipe(r, **a)
        if isinstance(h, bytes):
            h = h.decode('utf-8', 'replace')
        xml = _xml_word(RE.export_word_equipe(r, **a))
        wb = load_workbook(io.BytesIO(x))
        xl = ' | '.join(str(c.value) for ws in wb.worksheets
                        for row in ws.iter_rows() for c in row
                        if c.value is not None)
        wd = ' | '.join(_RE_WT.findall(xml))

        #: (a) plus aucune promesse fausse, dans aucun format
        restes = {n: t for n, t in (('Excel', xl), ('HTML', h), ('Word', wd))
                  if 'CLASSEMENT (A4)' in t or 'Modèle ML' in t}
        self.assertEqual(
            restes, {},
            f"{sorted(restes)} annonce(nt) encore un classement d'A4 alors "
            f"que la table porte celui d'A6 : un GLM et un modele DL y "
            f"figurent.")
        #: (b) la note atteint les TROIS, et c'est bien CELLE du jumeau
        absents = [n for n, t in (('Excel', xl), ('HTML', h), ('Word', wd))
                   if NOTE_CLASSEMENT not in t]
        self.assertEqual(
            absents, [],
            f"{absents} ne publie(nt) pas la note du classement. L'ordre y "
            f"suit le SCORE GLOBAL et non le Gini : sans la phrase, un "
            f"lecteur presse y voit une erreur de tri.")
        print(f"    RS-6 SCEAU : 0 titre fautif, note publiee aux 3 formats "
              f"({NOTE_CLASSEMENT[:38]}...)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
