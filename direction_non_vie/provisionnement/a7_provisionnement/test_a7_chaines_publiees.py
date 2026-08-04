# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 Ibrahim — verrou GÉNÉRIQUE sur les chaînes publiées (lot C1)
=============================================================================

 ⚠️ CE VERROU EST ÉCRIT EN PREMIER DU LOT C, ET C'EST DÉLIBÉRÉ.

 Le même défaut s'est produit SIX fois dans ce dépôt : un séparateur de
 milliers `.replace(',', ' ')` appliqué à la PHRASE entière au lieu du seul
 nombre. Il transforme « p < 0,01 » en « p < 0 01 » et « seule, soit » en
 « seule  soit ». Cinq fois dans la série B10, une sixième au lot A2 — alors
 que je venais de relire la note qui le décrivait.

 Un test par occurrence ne l'arrêtera jamais : il faut un verrou qui inspecte
 TOUT ce que l'agent publie. Le lot C va produire des centaines de lignes de
 texte ; écrit maintenant, ce verrou les protège à mesure qu'elles s'écrivent.
 Écrit à la fin, il n'aurait fait que constater.

 DEUX RÈGLES, ET LEUR PORTÉE EST DIFFÉRENTE — c'est la calibration qui l'a
 imposée, pas une intuition :

  · LE NOMBRE, partout, sans exception. Dans un nombre à séparateur d'espace,
    tous les groupes APRÈS le premier font exactement trois chiffres.
    « 1 564 926 » est légitime ; « 0 01 » (deux chiffres) et « 0 0294 »
    (quatre) sont le défaut. Zéro faux positif mesuré.

  · LA PONCTUATION, sur les lignes de PROSE seulement. Un double espace entre
    deux mots trahit une virgule mangée. Mais `n4['jugement']` est un TABLEAU
    à colonnes alignées où l'espacement est voulu : une ligne qui contient un
    alignement de trois espaces ou plus n'est pas une phrase. Sans cette
    distinction, le verrou criait 12 fois sur des alignements légitimes.

 CALIBRATION MESURÉE AVANT D'ÊTRE FIGÉE : 4 défauts sur 4 détectés, 3 cas
 légitimes sur 3 silencieux, et 0 signalement sur 1 619 chaînes réellement
 publiées par trois scénarios.
=============================================================================
"""

import io
import re
import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, RAA, _TRI_RECOURS)

#: Un nombre à séparateur d'espace : « 1 564 926 ».
#:
#: ⚠️ LE CHIFFRE NE DOIT PAS ÊTRE PRÉCÉDÉ D'UNE LETTRE, ET C'EST UN FAUX
#: POSITIF MESURÉ QUI L'A IMPOSÉ. Sans cette garde, « Q1 2025 » déclenchait le
#: verrou : la regex attrapait le « 1 » de « Q1 » et voyait un groupe de quatre
#: chiffres là où il n'y a qu'un trimestre suivi d'une année. L'angle mort
#: était GÉNÉRAL — « S2 2025 » tombait pareil, et « S2 » désigne Solvabilité 2
#: dans tout ce dépôt. Il a fallu qu'une chaîne de cette forme atteigne le
#: `n4` publié pour qu'il se révèle.
#: Un chiffre précédé d'une lettre appartient à un jeton alphanumérique — Q1,
#: S2, P99 — et n'ouvre jamais un montant formaté. Les quatre défauts réels
#: restent détectés : dans « p < 0 01 », « 0 0294 » et « 12 34 € », le premier
#: groupe est précédé d'une espace, jamais d'une lettre.
_NOMBRE_ESPACE = re.compile(r'(?<![A-Za-zÀ-ÿ])\d+(?: \d+)+')
#: Double espace entre deux caractères de mot — une virgule a sauté.
_DOUBLE_ESPACE = re.compile(r'(?<=[^\W\d_])  +(?=[^\W\d_])')
#: Trois espaces ou plus : la ligne aligne des colonnes, ce n'est pas de la prose.
_ALIGNEMENT = re.compile(r'   ')


def defauts_de_separateur(texte):
    """Rend les (genre, extrait) suspects d'une chaîne. Vide = propre."""
    trouves = []
    for m in _NOMBRE_ESPACE.finditer(texte):
        groupes = m.group(0).split(' ')
        mauvais = [g for g in groupes[1:] if len(g) != 3]
        if mauvais:
            debut, fin = m.span()
            trouves.append(
                ('groupe de %s chiffres au lieu de 3'
                 % ','.join(str(len(g)) for g in mauvais),
                 texte[max(0, debut - 30):fin + 18]))
    for ligne in texte.split('\n'):
        if _ALIGNEMENT.search(ligne):
            continue
        for m in _DOUBLE_ESPACE.finditer(ligne):
            d = m.start()
            trouves.append(('virgule remplacée par un espace',
                            ligne[max(0, d - 30):d + 30]))
    return trouves


def _chaines(obj, chemin='', acc=None):
    """Toutes les chaînes d'une structure, avec le chemin qui y mène."""
    acc = acc if acc is not None else []
    if isinstance(obj, str):
        acc.append((chemin, obj))
    elif isinstance(obj, dict):
        for cle, val in obj.items():
            _chaines(val, f'{chemin}.{cle}', acc)
    elif isinstance(obj, (list, tuple)):
        for i, val in enumerate(obj):
            _chaines(val, f'{chemin}[{i}]', acc)
    return acc


def _run_complet(triangle, **kw):
    """Un run avec TOUS les livrables — le verrou de vocabulaire les inspecte."""
    src = np.asarray(triangle, dtype=float)
    return AgentA7Provisionnement(verbose=False).run(
        source=src, mode_declare='cumule', generer_graphiques=True,
        generer_word=True, n_sim_bootstrap=60, seed=42, **kw)


def _run(triangle, **kw):
    src = np.asarray(triangle, dtype=float)
    kw.setdefault('primes', np.full(src.shape[0],
                                    float(np.nanmean(src[:, 0])) * 8.0))
    return AgentA7Provisionnement(verbose=False).run(
        source=src, mode_declare='cumule', generer_graphiques=False,
        generer_word=False, n_sim_bootstrap=60, seed=42, **kw)


# =============================================================================
#  T1 — LE DÉTECTEUR DISCRIMINE, DANS LES DEUX SENS
# =============================================================================

class T1_Le_Detecteur_Discrimine(unittest.TestCase):
    """Un verrou qui ne peut pas se déclencher ne protège rien."""

    #: Les défauts RÉELS, repris tels qu'ils sont sortis du code.
    _DEFAUTS = (
        "L'hypothèse est non validée sur la colonne 0 (p < 0 01) que ces "
        "années doivent traverser",
        "Elles sont portées par Chain Ladder seule  soit 4 625 811 € du total",
        "réserve portée de 17 469 539 € à 59 400 660 €, écart de 0 0294",
        "provision de 12 34 € sur l'exercice",
    )

    #: Ce qui est LÉGITIME et ne doit jamais crier.
    _SAINS = (
        "réserve 1 564 926 €, p < 0,01, soit 26,3 % du Best Estimate",
        # ⚠️ LES DEUX FORMES QUI ONT RÉVÉLÉ L'ANGLE MORT (lot « courbe »).
        "EIOPA RFR Term Structures — Q1 2025",
        "SCR PROVISIONS (Art. 115 S2 2025)",
        "BE = 18 680 856 € · σ = 2 447 095 € · CV = 13,1 %",
        "  Chain Ladder      réserve=18 680 856   poids=53%",
        "H2 Stabilité      : VALIDÉE       CV=7.9%  dérive=6.8",
        "Années [5, 6, 7, 8] : couverture à justifier",
    )

    def test_il_attrape_les_defauts_reels(self):
        for s in self._DEFAUTS:
            self.assertTrue(defauts_de_separateur(s),
                            f"défaut non détecté : {s[:60]}")
        print(f"    OK C1-1 les {len(self._DEFAUTS)} défauts réels sont "
              f"détectés")

    def test_il_se_tait_sur_ce_qui_est_legitime(self):
        for s in self._SAINS:
            self.assertEqual(defauts_de_separateur(s), [],
                             f"faux positif sur : {s[:60]}")
        print(f"    OK C1-2 les {len(self._SAINS)} cas légitimes ne "
              f"déclenchent rien — dont un tableau à colonnes alignées")


# =============================================================================
#  T2 — TOUT CE QUE L'AGENT PUBLIE EST INSPECTÉ
# =============================================================================

class T2_Aucune_Chaine_Publiee_N_Est_Fautive(unittest.TestCase):

    def test_les_resultats_de_trois_scenarios(self):
        """n1, n2, n3, n4 et le commentaire, récursivement."""
        total, fautes = 0, []
        for nom, tri in (('GenIns', GENINS), ('RAA', RAA),
                         ('Recours', _TRI_RECOURS)):
            r = _run(tri)
            bloc = {'n1': r.get('n1'), 'n2': r['n2'], 'n3': r['n3'],
                    'n4': r['n4'], 'commentaire': r.get('commentaire')}
            for chemin, s in _chaines(bloc):
                total += 1
                for genre, extrait in defauts_de_separateur(s):
                    fautes.append(f'{nom}{chemin} — {genre} : {extrait!r}')
        self.assertEqual(fautes, [], '\n'.join(fautes[:10]))
        print(f"    OK C1-3 {total} chaînes publiées sur 3 scénarios, "
              f"aucune fautive")

    def test_les_cellules_de_l_excel(self):
        """Le format que le défaut atteindrait sans qu'on le voie."""
        import openpyxl
        r = _run(GENINS)
        octets = r.get('excel_bytes') or b''
        if not octets:
            self.skipTest('openpyxl absent')
        wb = openpyxl.load_workbook(io.BytesIO(octets))
        total, fautes = 0, []
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    if not isinstance(c.value, str):
                        continue
                    total += 1
                    for genre, extrait in defauts_de_separateur(c.value):
                        fautes.append(f'{ws.title}!{c.coordinate} — {genre} : '
                                      f'{extrait!r}')
        self.assertEqual(fautes, [], '\n'.join(fautes[:10]))
        print(f"    OK C1-4 {total} cellules de texte dans l'Excel, "
              f"aucune fautive")



# =============================================================================
#  T3 — LE VERROU DE VOCABULAIRE « SCR »  (lot C3b)
# =============================================================================
#
#  ⚠️ MÊME DISPOSITIF QUE LE VERROU DE SÉPARATEUR CI-DESSUS, ET POUR LA MÊME
#  RAISON : le mot « SCR » désignait QUATRE grandeurs différentes dans les
#  livrables. Le relevé exhaustif du lot C3b a compté 110 occurrences, 70
#  formulations distinctes — et sept d'entre elles nommaient « SCR » un NIVEAU
#  de réserve. Corriger les sept sans poser de verrou, c'est attendre la
#  huitième : C3c et C3d vont ajouter des graphiques et du routage.
#
#  LA CONVENTION, EN TROIS RÈGLES :
#    1. « SCR » désigne UNE grandeur, la charge de capital de l'article 115
#       (3·σ·V). C'est une MARGE, jamais un niveau de réserve.
#    2. Un niveau de percentile se nomme par son percentile — « Réserve au
#       P99,5 » — jamais « SCR ».
#    3. Une marge issue d'un percentile se nomme comme telle, « Marge
#       P99,5 − BE » : c'est elle, et non le niveau, qui se compare au SCR.
#
#  L'UNITÉ D'ANALYSE EST ATOMIQUE, ET C'EST LA CALIBRATION QUI L'A IMPOSÉ :
#  une CELLULE d'un tableau, une étiquette de figure, une LIGNE de prose —
#  jamais une ligne de tableau entière. Le Word aligne « P90 (composé) » et
#  « SCR Provisions » dans deux cellules voisines : les aplatir ferait crier le
#  verrou sur une mise en page parfaitement correcte.
#
#  CALIBRÉ AVANT D'ÊTRE FIGÉ, DANS LES DEUX SENS : 7 défauts réels sur 7
#  détectés, 8 formulations légitimes sur 8 silencieuses, et 0 signalement sur
#  9 045 unités réellement publiées par deux configurations d'exposition.
# =============================================================================

#: Le mot, isolé.
_SCR = re.compile(r'\bSCR\b')
#: Un percentile, sous toutes ses écritures — « P99.5 », « 99,5 », « 99.5th ».
_PERCENTILE = re.compile(
    r'\bP\s?\d{2,3}([.,]\d)?\b|\bpercentile\b|\bquantile\b|\b\d{2}[.,]\d',
    re.I)
#: Ce qui prouve qu'on parle bien de l'article 115 — et non d'un percentile.
_ART115 = re.compile(
    r'[Aa]rt(icle)?\.?\s*11[57]|3\s*[×x]\s*σ|3\s*[×x]\s*\d'
    r'|SCR\s*/\s*BE|ratio SCR|formule standard', re.I)


def vocabulaire_scr_fautif(unite):
    """True si cette unité publiée nomme « SCR » un niveau de percentile."""
    if not _SCR.search(unite) or not _PERCENTILE.search(unite):
        return False
    return not _ART115.search(unite)


def _unites_publiees(r):
    """Les unités ATOMIQUES d'un run — cellules, étiquettes, lignes de prose."""
    out = []
    for cle in ('n2', 'n3', 'n4'):
        for chemin, s in _chaines(r.get(cle), cle):
            out += [(chemin, ligne) for ligne in s.split('\n')]
    for ligne in (r.get('commentaire') or '').split('\n'):
        out.append(('commentaire', ligne))
    for nom, fig in (r.get('graphiques') or {}).items():
        for chemin, s in _chaines(fig.to_plotly_json(), 'figure:' + nom):
            out.append((chemin, s))
    octets = r.get('excel_bytes') or b''
    if octets:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(octets))
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str):
                        out.append(('excel:%s!%s' % (ws.title, c.coordinate),
                                    c.value))
    mot = r.get('word_bytes') or b''
    if mot:
        import docx
        doc = docx.Document(io.BytesIO(mot))
        for p in doc.paragraphs:
            out.append(('word', p.text))
        for tbl in doc.tables:
            for row in tbl.rows:
                for c in row.cells:       # CELLULE, jamais la ligne entière
                    out.append(('word:cellule', c.text))
    return out


class T3_Le_Mot_SCR_Ne_Nomme_Qu_Une_Grandeur(unittest.TestCase):

    #: Les défauts RÉELS, tels qu'ils sortaient du code avant le lot C3b.
    _DEFAUTS = (
        'SCR (P99.5)',                          # g7, segment n°4
        'Bootstrap P99.5 (SCR)',                # Excel, onglet Sensibilités
        'P99.5 — SCR provisions',               # Excel, onglet Bootstrap
        'P99.5 — SCR provisions (composé)',     # Excel, onglet Résultats
        'SCR provisions — extrême (99.5th)',    # Excel, colonne Lecture
        '<b>P99.5 (SCR)</b><br>25,040,191€',    # g6, annotation
        "Le P99.5 Bootstrap de 25 040 191 € constitue l'estimation "
        "stochastique du SCR provisions — comparable du P99.5 Mack.",
    )

    #: Ce qui est LÉGITIME : le SCR de l'article 115, sous ses formes réelles.
    _SAINS = (
        'SCR_prov = 3 × 11.0% × 17,571,609€ = 5,798,631€ (ratio SCR/BE = 33.0%)',
        'Ratio SCR/BE',
        'SCR PROVISIONS (Art. 115 S2)',
        'CALCUL SCR PROVISIONS (LoB unique)',
        "Le facteur 3 correspond au quantile 99.5% d'une loi normale",
        'P99.5 — Provision extrême (composé)',
        'SCR Provisions — Formule standard Art. 115 Règlement Délégué (UE) 2015/35',
        "c'est cette marge, et non le niveau, qui se compare au SCR de "
        "l'article 115. Elle est proche de celle du P99.5 Mack.",
    )

    def test_il_attrape_les_sept_defauts_du_releve(self):
        for s in self._DEFAUTS:
            self.assertTrue(vocabulaire_scr_fautif(s),
                            'défaut non détecté : %s' % s[:70])
        print('    OK C3b-1 les %d défauts du relevé exhaustif sont détectés'
              % len(self._DEFAUTS))

    def test_il_se_tait_sur_l_article_115(self):
        for s in self._SAINS:
            self.assertFalse(vocabulaire_scr_fautif(s),
                             'faux positif sur : %s' % s[:70])
        print('    OK C3b-2 les %d formulations légitimes restent silencieuses'
              % len(self._SAINS))

    def test_aucune_unite_publiee_ne_nomme_scr_un_percentile(self):
        """Tout ce que l'agent publie, avec et sans exposition."""
        n = np.asarray(GENINS).shape[0]
        total, fautes = 0, []
        for kw in ({'primes': np.full(n, 4e6)}, {}):
            r = _run_complet(GENINS, **kw)
            for ou, u in _unites_publiees(r):
                total += 1
                if vocabulaire_scr_fautif(u):
                    fautes.append('%s — %r' % (ou, re.sub(r'\s+', ' ', u)[:90]))
        self.assertEqual(fautes, [], '\n'.join(fautes[:10]))
        print('    OK C3b-3 %d unités publiées, aucune ne nomme « SCR » un '
              'niveau de percentile' % total)

if __name__ == '__main__':
    unittest.main(verbosity=2)
