# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 — LE PROFIL DE RUN-OFF DE LA RISK MARGIN EST CELUI DU TRIANGLE
=============================================================================

 CE QUE CE FICHIER TIENT, ET POURQUOI IL EXISTE À CÔTÉ DE T4.

 `test_a7_gouvernance.T4_Zero_Euro_Deplace` gèle des EUROS. C'est nécessaire
 et ce n'est pas suffisant : une Risk Margin en euros bouge à chaque arrêté de
 courbe EIOPA, si bien que sa valeur gelée doit être révisée régulièrement — et
 pendant des mois elle a gelé un chiffre FAUX sans que rien ne le dise. Le
 garde-fou était bon ; son étalon ne l'était pas.

 Ce fichier gèle une PROPRIÉTÉ, qui elle ne dépend d'AUCUNE courbe : le profil
 d'écoulement publié doit être celui du triangle qu'il projette. On le mesure
 contre un oracle recalculé ICI, sans rien importer de N4 :

     compléter le carré par Chain Ladder, puis
     BE(t) = Σ_i (ultime_i − payé_i(t))     où l'année i est à l'âge k_i + t

 ⚠️ LE DÉFAUT QUE CE FICHIER EMPÊCHE DE REVENIR. `_calculer_risk_margin`
 posait `pct_res[j] = 1/f_cum[j]` en le commentant « la part encore à
 développer ». `1/f_cum[j]` est la part DÉJÀ développée — c'est mot pour mot ce
 que documente `calculer_pct_developpe`. Le profil déclarait donc que 99 % de
 la réserve restait à payer après un an sur un triangle à dix ans de
 développement, et gonflait la Risk Margin de 115 % (GenIns : 2 078 603 €
 publiés contre 968 523 €).

 ⚠️ LA VIOLATION EST PLANTÉE DANS LE TEST LUI-MÊME. `T3` reconstruit le profil
 fautif et exige qu'il ÉCHOUE au seuil que le profil publié franchit. Un seuil
 qu'aucun des deux ne distingue serait un seuil qui ne mesure rien : ce test
 vérifie que le sien discrimine, au lieu de le supposer.
=============================================================================
"""

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS, RAA)

#: Écart quadratique moyen — la MOYENNE DES CARRÉS, pas sa racine. L'unité est
#: dite ici parce que le commentaire d'origine du profil confondait déjà les
#: deux, et parce qu'un seuil dont on ignore l'unité ne protège rien.
#:
#: Mesuré, en EQM : le profil juste rend 0,0000 sur GenIns et RAA, et au pire
#: 0,00054 sur un triangle dont les ultimes varient de x21 entre années (la
#: forme en somme de queue est exacte à ultimes égaux, et se dégrade lentement
#: sinon). Le profil de la part DÉJÀ développée rend 0,0707 et 0,0806.
#: Le seuil est placé à 0,01 : environ 17x au-dessus du pire cas juste mesuré,
#: et 7x en dessous du meilleur cas fautif. `T3` vérifie qu'il sépare
#: réellement les deux, au lieu de le supposer.
SEUIL_EQM = 0.01


def _oracle_runoff(C):
    """BE(t)/BE(0) recalculé À LA MAIN, sans rien importer de N4.

    Facteurs Chain Ladder volume-weighted sur la zone connue, complétion du
    carré, puis run-off en avançant la diagonale d'un cran par période.
    """
    C = np.asarray(C, dtype=float)
    n, m = C.shape
    f = np.ones(m - 1)
    for j in range(m - 1):
        num = den = 0.0
        for i in range(n):
            if i + j + 1 >= n:
                break
            if C[i, j] > 0 and C[i, j + 1] > 0:
                num += C[i, j + 1]
                den += C[i, j]
        f[j] = num / den if den > 0 else 1.0

    F = C.copy()
    for i in range(n):
        for j in range(n - i, m):
            F[i, j] = F[i, j - 1] * f[j - 1]

    ult = F[:, m - 1]
    be = []
    for t in range(m + 15):
        paye = np.array([F[i, min(n - 1 - i + t, m - 1)] for i in range(n)])
        be.append(float(np.sum(ult - paye)))
    return [x / be[0] for x in be] if be[0] > 0 else []


def _eqm(a, b):
    """Écart quadratique moyen sur la longueur commune."""
    k = min(len(a), len(b))
    return sum((a[t] - b[t]) ** 2 for t in range(k)) / k


def _profil_publie(n4):
    """Le profil que N4 a RÉELLEMENT publié, lu dans sa table de run-off."""
    be_0 = float(n4['best_estimate'])
    return [float(ligne['be_t']) / be_0
            for ligne in (n4.get('tableau_run_off') or [])]


def _profil_part_deja_developpee(f_cum):
    """LE DÉFAUT, reconstruit : `pct_res[j] = 1/f_cum[j]`, la part DÉJÀ payée."""
    pct = [1.0 / max(float(x), 1.0) for x in f_cum]
    tot = max(sum(pct), 1e-10)
    m = len(pct)
    return [1.0 if t == 0 else (sum(pct[t:]) / tot if t < m else 0.0)
            for t in range(m + 15)]


def _run(triangle):
    src = np.asarray(triangle, dtype=float)
    return AgentA7Provisionnement(verbose=False).run(
        source=src, mode_declare='cumule', generer_graphiques=False,
        generer_word=False, generer_html=False, n_sim_bootstrap=30, seed=42)


class _Socle(unittest.TestCase):
    """Deux runs, partagés par les trois classes : la gate A7 est lente."""

    @classmethod
    def setUpClass(cls):
        cls.runs = {nom: _run(t)
                    for nom, t in (('GenIns', GENINS), ('RAA', RAA))}


# =============================================================================
#  T1 — LE PROFIL PUBLIÉ EST CELUI DU TRIANGLE
# =============================================================================

class T1_Le_Profil_Suit_Le_Run_Off(_Socle):

    def test_le_profil_publie_reproduit_le_run_off_du_triangle(self):
        for nom, tri in (('GenIns', GENINS), ('RAA', RAA)):
            n4 = self.runs[nom]['n4']
            publie = _profil_publie(n4)
            self.assertTrue(publie, "%s : table de run-off vide" % nom)
            oracle = _oracle_runoff(np.asarray(tri, dtype=float))
            e = _eqm(oracle, publie)
            self.assertLess(
                e, SEUIL_EQM,
                "%s : le profil publié s'écarte du run-off du triangle "
                "(EQM %.4f >= %s). Le profil d'écoulement de la Risk Margin "
                "doit être la part ENCORE à développer, `1 - 1/f_cum[j]`, et "
                "non `1/f_cum[j]` qui est la part DÉJÀ développée."
                % (nom, e, SEUIL_EQM))
            print("    OK PA1-1 %s : profil publié = run-off du triangle, "
                  "EQM %.4f < %s" % (nom, e, SEUIL_EQM))


# =============================================================================
#  T2 — LA PREMIÈRE PÉRIODE ÉCOULE VRAIMENT
# =============================================================================

class T2_La_Premiere_Periode_Ecoule(_Socle):
    """Propriété la moins chère, et celle qui aurait suffi à voir le défaut."""

    def test_la_reserve_perd_une_part_substantielle_la_premiere_annee(self):
        for nom in ('GenIns', 'RAA'):
            publie = _profil_publie(self.runs[nom]['n4'])
            self.assertGreater(len(publie), 1, "%s : run-off trop court" % nom)
            self.assertLess(
                publie[1], 0.85,
                "%s : BE(1)/BE(0) = %.4f. Un triangle à dix ans de "
                "développement ne conserve pas 85 %% de sa réserve après un "
                "an — le profil fautif publiait 0,9896." % (nom, publie[1]))
            print("    OK PA1-2 %s : BE(1)/BE(0) = %.4f < 0,85"
                  % (nom, publie[1]))


# =============================================================================
#  T3 — LA VIOLATION PLANTÉE : le seuil sépare-t-il vraiment les deux profils ?
# =============================================================================

class T3_Le_Seuil_Discrimine(_Socle):
    """⚠️ SANS CETTE CLASSE, T1 pourrait passer avec un seuil qui ne mesure
    rien. On reconstruit ICI le profil fautif et on exige qu'il ÉCHOUE."""

    def test_le_profil_de_la_part_deja_developpee_echoue_au_meme_seuil(self):
        for nom, tri in (('GenIns', GENINS), ('RAA', RAA)):
            r = self.runs[nom]
            f_cum = list(r['n3']['chain_ladder']['facteurs_cumules'])
            oracle = _oracle_runoff(np.asarray(tri, dtype=float))
            e_faux = _eqm(oracle, _profil_part_deja_developpee(f_cum))
            e_vrai = _eqm(oracle, _profil_publie(r['n4']))
            self.assertGreater(
                e_faux, SEUIL_EQM,
                "%s : le profil de la part DÉJÀ développée passerait le seuil "
                "— le seuil ne discrimine plus, il ne mesure rien." % nom)
            self.assertLess(
                e_vrai * 5, e_faux,
                "%s : le profil publié n'est pas franchement meilleur que le "
                "profil fautif (%.4f contre %.4f)." % (nom, e_vrai, e_faux))
            print("    OK PA1-3 %s : publié %.4f < %s < %.4f part déjà "
                  "développée" % (nom, e_vrai, SEUIL_EQM, e_faux))

    def test_f_cum_est_dans_l_ordre_naturel_decroissant(self):
        """⚠️ GARDE LA PROSE, PAS SEULEMENT LE CALCUL. Le commentaire du profil
        a affirmé pendant des mois que `f_cum` était dans l'ordre
        [CDF_dernière_col, …, CDF_1ère_col]. Il ne l'est pas, et un lecteur qui
        vérifiait le profil en s'y fiant concluait qu'il était juste."""
        for nom in ('GenIns', 'RAA'):
            f_cum = [float(x) for x in
                     self.runs[nom]['n3']['chain_ladder']['facteurs_cumules']]
            self.assertGreater(
                f_cum[0], f_cum[-1],
                "%s : f_cum[0]=%.4f devrait être la CDF de la PREMIÈRE "
                "colonne, donc la plus grande." % (nom, f_cum[0]))
            self.assertAlmostEqual(
                f_cum[-1], 1.0, places=6,
                msg="%s : la dernière CDF doit valoir 1,0 (rien ne reste à "
                    "développer au-delà de la dernière colonne)." % nom)
            print("    OK PA1-4 %s : f_cum décroissant, %.4f -> %.4f"
                  % (nom, f_cum[0], f_cum[-1]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
