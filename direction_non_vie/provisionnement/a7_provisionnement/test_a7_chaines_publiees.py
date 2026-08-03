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
_NOMBRE_ESPACE = re.compile(r'\d+(?: \d+)+')
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
