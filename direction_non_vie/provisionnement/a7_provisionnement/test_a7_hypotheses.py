# =============================================================================
#  H2 NE PUBLIE PLUS DE MESURE QU'IL N'A PRISE
# =============================================================================
#
#  ⚠️ GATE : `py -m unittest discover -s direction_non_vie -t .`
#
#  ⚠️ POURQUOI CE FICHIER EXISTE, ET POURQUOI IL N'EXISTAIT PAS. Des quatre
#  modules d'hypothèses d'A7, trois ont leur fichier de test —
#  `test_a7_hypotheses_clm`, `_bfcc`, `_bootstrap`. `n2_hypotheses.py`, le
#  cadre historique qui pilote ENCORE le score, la sélection des méthodes et le
#  commentaire signé, n'en avait aucun. C'est aussi le seul des quatre où le
#  relevé B1 a trouvé des affirmations fausses publiées. La corrélation n'est
#  pas une coïncidence, c'est l'explication : corriger sans poser de filet
#  aurait reproduit la cause.
#
#  ─────────────────────────────────────────────────────────────────────────────
#  CE QUE LE LOT FERME, ET CE QUE CHAQUE CLASSE VERROUILLE
#
#  Mesuré AVANT correction, sur un triangle 3×3 parfaitement sain, LoB
#  `credit_caution` (seuils réels 20 % / 30 %). Le commentaire signé publiait :
#
#      H2 — STABILITÉ DES FACTEURS : VALIDÉE [score 80/100]
#      Le coefficient de variation moyen [...] est de 0.0% (seuil branche :
#      15.0%), et la dérive temporelle est de 0.0% (seuil : 20.0%). Les
#      facteurs sont stables dans le temps : les années récentes se
#      développent de la même façon que les années anciennes.
#
#  Sur ZÉRO colonne testée. Quatre faussetés dans un paragraphe : un verdict,
#  deux mesures qui n'existent pas, un constat sur le portefeuille, et des
#  seuils qui sont ceux du générique et non de la branche. Trois lignes plus
#  bas, BFCC-H2 et BOOT-H2 écrivaient NON TESTABLE sur le même triangle.
#
#  ⚠️ LE VERDICT INTERNE NE BOUGE PAS — c'est `A1_Aucun_Euro_Ne_Se_Deplace` qui
#  le tient. `ok`, `score`, `cv_moy`, `derive_moy`, `ok_cv`, `ok_derive` gardent
#  EXACTEMENT les valeurs d'avant le lot, parce que N4 les lit pour composer le
#  Best Estimate. Ce lot corrige ce qui est ÉCRIT, pas ce qui est décidé — même
#  arbitrage qu'au lot A1 pour H1. Les valeurs attendues ci-dessous ont été
#  RELEVÉES sur le code d'avant : ce sont des oracles, pas des recopies.
# =============================================================================

import ast
import inspect
import unittest

import numpy as np

from . import n2_hypotheses as _n2h
from . import n5_commentaire as _n5c
from .n2_hypotheses import HypothesesValidator
from .n5_commentaire import _s3_hypotheses

#: ⚠️ 3×3 : colonne 0 porte 2 facteurs, colonne 1 en porte 1 — jamais les 3
#: qu'exige `_tester_h2_stabilite`. `cv_cols` reste vide. Rien de pathologique
#: dans ce triangle : il est strictement croissant.
COURT = np.array([[100.0, 150.0, 180.0],
                  [120.0, 170.0,   0.0],
                  [130.0,   0.0,   0.0]])

#: ⚠️ 4×4 : colonne 0 porte EXACTEMENT 3 facteurs — assez pour le CV, pas assez
#: pour la dérive, qui exige 4 (`mid >= 2`). C'est le seul cas où le CV est
#: mesuré et la dérive ne l'est pas, et il se produit sur un triangle ordinaire.
MOYEN = np.array([[1000.0, 1400.0, 1600.0, 1700.0],
                  [1100.0, 1560.0, 1780.0,    0.0],
                  [1200.0, 1660.0,    0.0,    0.0],
                  [1300.0,    0.0,    0.0,    0.0]])

#: 5×5 : deux colonnes testables, dérive calculée. Le cas nominal.
LONG = np.array([[1000.0, 1400.0, 1600.0, 1700.0, 1750.0],
                 [1100.0, 1550.0, 1770.0, 1880.0,    0.0],
                 [1200.0, 1680.0, 1900.0,    0.0,    0.0],
                 [1300.0, 1830.0,    0.0,    0.0,    0.0],
                 [1400.0,    0.0,    0.0,    0.0,    0.0]])

#: ⚠️ LoB DONT LES SEUILS NE SONT PAS LES GÉNÉRIQUES, ET C'EST TOUT L'INTÉRÊT.
#: `credit_caution` vaut 20 % / 30 % quand le générique vaut 15 % / 20 %. Un
#: test conduit sur `generique` n'aurait RIEN vu : les deux valeurs coïncident.
#: Dix LoB sur quinze diffèrent du générique — mesuré sur `lob_config`.
LOB = 'credit_caution'
LOB_CV, LOB_DERIVE = 0.20, 0.30

#: La phrase exacte que le rapport publiait sur zéro mesure. Elle est ici en
#: toutes lettres pour qu'une recherche plein texte la retrouve le jour où elle
#: reviendrait — un constat sur le portefeuille ne se déduit pas d'un défaut.
CONSTAT_INTERDIT = ("les années récentes se développent de la même façon que "
                    "les années anciennes")

#: `n5_excel` et `n5_rapport` tronquent le message à 200 caractères.
TRONCATURE = 200


def _h2(C, lob=LOB):
    return HypothesesValidator().valider(C, lob=lob)['h2_stabilite']


def _texte(C, lob=LOB):
    return _s3_hypotheses(HypothesesValidator().valider(C, lob=lob))


class A1_Aucun_Euro_Ne_Se_Deplace(unittest.TestCase):
    """⚠️ LE VERROU DU LOT. Si l'un de ces champs bouge, N4 recompose le Best
    Estimate autrement et le lot a dépassé son mandat."""

    def test_le_chemin_non_testable_rend_les_memes_valeurs(self):
        h = _h2(COURT)
        # Oracles relevés sur le code d'AVANT le lot.
        self.assertIs(h['ok'], True)
        self.assertEqual(h['score'], 80)
        self.assertEqual(h['cv_moy'], 0)
        self.assertEqual(h['derive_moy'], 0)
        self.assertIs(h['ok_cv'], True)
        self.assertIs(h['ok_derive'], True)
        print('    OK A1-1 le verdict interne est inchange (zero colonne)')

    def test_le_chemin_nominal_rend_les_memes_valeurs(self):
        h = _h2(LONG)
        self.assertIs(h['ok'], True)
        self.assertEqual(h['score'], 98)
        self.assertAlmostEqual(h['cv_moy'], 0.0046, places=4)
        self.assertAlmostEqual(h['derive_moy'], 0.0005, places=4)
        print('    OK A1-2 le verdict interne est inchange (nominal)')


class B1_Zero_Colonne_Testee(unittest.TestCase):
    """⚠️ « VALIDÉE [score 80/100] » SUR RIEN — le defaut central du lot."""

    def test_le_module_dit_non_testable(self):
        h = _h2(COURT)
        self.assertEqual(h['statut'], 'NON TESTABLE')
        self.assertEqual(h['n_colonnes_testees'], 0)
        self.assertIs(h['derive_calculee'], False)
        print('    OK B1-1 le module publie NON TESTABLE et son assiette')

    def test_la_narration_ne_dit_plus_validee(self):
        txt = _texte(COURT)
        self.assertIn('H2 — STABILITÉ DES FACTEURS : NON TESTABLE', txt)
        self.assertNotIn('H2 — STABILITÉ DES FACTEURS : VALIDÉE', txt)
        print('    OK B1-2 la narration ne publie plus VALIDEE sur zero test')

    def test_la_narration_n_affirme_rien_sur_le_portefeuille(self):
        # ⚠️ LA FAUSSETÉ LA PLUS GRAVE : un constat, pas un score.
        self.assertNotIn(CONSTAT_INTERDIT, _texte(COURT))
        print('    OK B1-3 le constat sur le portefeuille a disparu')

    def test_aucun_chiffre_de_stabilite_n_est_publie(self):
        # Les zéros par défaut ne doivent plus paraître comme des mesures.
        txt = _texte(COURT)
        for faux in ('est de 0.0%', 'est de 0,0%', 'dérive temporelle est de'):
            self.assertNotIn(faux, txt, f'{faux!r} est encore publie')
        print('    OK B1-4 les zeros par defaut ne sont plus affiches')

    def test_le_motif_du_module_est_cite(self):
        # Même règle qu'en H1 : on cite, on ne parse pas.
        self.assertIn(_h2(COURT)['message'], _texte(COURT))
        print('    OK B1-5 le motif du module est cite mot pour mot')


class C1_Les_Seuils_Sont_Ceux_De_La_Branche(unittest.TestCase):
    """⚠️ 15 % ET 20 % ÉTAIENT PUBLIÉS SOUS LE MOT « BRANCHE ». Ils venaient du
    repli générique : `_h2` ne publiait pas ses seuils sur ce chemin."""

    def test_le_module_publie_les_seuils_meme_sans_test(self):
        h = _h2(COURT)
        self.assertEqual(h['seuil_cv'], LOB_CV)
        self.assertEqual(h['seuil_derive'], LOB_DERIVE)
        print('    OK C1-1 les seuils de la branche sont publies (zero test)')

    def test_la_narration_publie_le_seuil_de_la_branche(self):
        txt = _texte(MOYEN)
        self.assertIn('seuil branche : 20.0%', txt)
        self.assertNotIn('seuil branche : 15.0%', txt)
        print('    OK C1-2 la narration publie 20% et non le generique 15%')


class D1_La_Derive_Non_Calculee(unittest.TestCase):
    """⚠️ UNE DÉRIVE JAMAIS CALCULÉE VALAIT 0,0 % ET SE LISAIT « AUCUNE
    DÉRIVE ». Chemin ordinaire, pas un repli."""

    def test_le_module_dit_qu_il_ne_l_a_pas_calculee(self):
        h = _h2(MOYEN)
        self.assertEqual(h['n_colonnes_testees'], 1)
        self.assertIs(h['derive_calculee'], False)
        self.assertIn('NON CALCULÉE', h['message'])
        print('    OK D1-1 le module signale la derive non calculee')

    def test_la_narration_ne_certifie_pas_la_stabilite_dans_le_temps(self):
        txt = _texte(MOYEN)
        self.assertIn("LA DÉRIVE TEMPORELLE N'A PAS ÉTÉ CALCULÉE", txt)
        self.assertNotIn(CONSTAT_INTERDIT, txt)
        print('    OK D1-2 la stabilite dans le temps n est plus affirmee')

    def test_le_cv_mesure_reste_publie(self):
        # ⚠️ NE PAS SUR-CORRIGER : le CV, lui, A été mesuré. Le taire
        # retirerait une information juste.
        self.assertIn('est de 1.2%', _texte(MOYEN))
        print('    OK D1-3 le CV reellement mesure reste publie')


class E1_Aucune_Regression_Sur_Un_Triangle_NORMAL(unittest.TestCase):
    """⚠️ UN FILET QUI DÉGRADE LE CAS NOMINAL SE FAIT DÉSACTIVER."""

    def test_le_texte_nominal_est_intact(self):
        txt = _texte(LONG)
        self.assertIn('H2 — STABILITÉ DES FACTEURS : VALIDÉE', txt)
        self.assertIn(CONSTAT_INTERDIT, txt)
        self.assertIn('dérive temporelle est de', txt)
        print('    OK E1-1 le triangle nominal publie le texte d avant')

    def test_un_dict_ancien_produit_le_texte_d_avant(self):
        # ⚠️ LE REPLI EST CALIBRÉ POUR CELA. Un dict sans `statut` ni
        # `derive_calculee` — ancienne exécution, fixture écrite à la main —
        # doit produire EXACTEMENT le texte d'avant le lot, sinon le lot
        # casserait la lecture d'un résultat archivé.
        n2 = {'h2_stabilite': {'ok': True, 'score': 80, 'cv_moy': 0.05,
                               'derive_moy': 0.03, 'seuil_cv': 0.15,
                               'seuil_derive': 0.20}}
        txt = _s3_hypotheses(n2)
        self.assertIn('H2 — STABILITÉ DES FACTEURS : VALIDÉE', txt)
        self.assertIn(CONSTAT_INTERDIT, txt)
        print('    OK E1-2 un dict ancien produit le texte d avant')


class F1_Le_Motif_Survit_A_LA_Troncature(unittest.TestCase):
    """⚠️ DEUX LIVRABLES COUPENT LE MESSAGE À 200 CARACTÈRES. Un motif coupé en
    deux publierait « les zéros publiés sont des valeurs par… » — pire que pas
    de motif, parce que la phrase qui les disqualifie disparaît."""

    def test_le_motif_non_testable_tient_entier(self):
        msg = _h2(COURT)['message']
        self.assertLessEqual(len(msg), TRONCATURE)
        self.assertEqual(msg, msg[:TRONCATURE])
        print(f'    OK F1-1 le motif NON TESTABLE tient en {len(msg)} car.')

    def test_la_derive_non_calculee_survit_a_la_coupe(self):
        # Ce message-ci dépasse 200 ; ce qui compte est que l'essentiel soit
        # AVANT la coupe.
        self.assertIn('NON CALCULÉE', _h2(MOYEN)['message'][:TRONCATURE])
        print('    OK F1-2 « NON CALCULEE » survit a la troncature')


# =============================================================================
#  LOT F1 + F2 — LE TEXTE DIT CE QUE LE TEST TESTE, ET NE PRESCRIT PLUS SANS
#  FONDEMENT
# =============================================================================
#
#  ⚠️ CES DEUX DÉFAUTS ONT ÉTÉ TRACÉS PAR CONSOMMATEUR, PAS PAR MODULE — et
#  c'est ce qui a fait la différence. Le relevé B1, conduit module par module,
#  avait vu 1 site de F2 ; la trace par la prose en a trouvé SIX, dont deux
#  dans `n5_commentaire` et **deux que j'avais écrits moi-même au lot A1**.
#  A1 avait corrigé l'ASSIETTE de H1 et laissé la caractérisation de ce que le
#  test PROUVE.
#
#  F1 n'était pas une phrase mais une PRÉMISSE sous quatre recommandations,
#  dont un « obligatoire ». Mesuré sur un portefeuille en croissance, l'année
#  récente portant le plus gros volume ET le facteur le plus élevé (1,6000) :
#        standard         f0 = 1,5808   <- le PLUS proche
#        volume_weighted  f0 = 1,5674   <- le plus LOIN
#  `volume_weighted` donne donc MOINS de poids aux années récentes, dans le cas
#  même que le texte invoquait.

#: Les formes exactes qui ne doivent plus être PUBLIÉES. Écrites en toutes
#: lettres pour qu'une recherche plein texte les retrouve si elles revenaient.
INTERDITES = (
    "années de survenance sont indépendantes",
    "années de survenance se développent",
    "systématiquement différent des autres",
    "favorise les années récentes",
    "plus de poids aux années récentes",
    "pondère par C[i,j]",
    "volume_weighted doit être",
    "volume_weighted est obligatoire",
    "volume_weighted recommandée",
)

#: ⚠️ UNE FAUSSETÉ PEUT APPARAÎTRE DANS UNE PHRASE QUI LA DÉSAVOUE, ET SEULEMENT
#: LÀ. Même discriminant que le garde-fou du message de commit : c'est la FORME
#: qui décide, jamais le mot. Sans cette porte, le test refuserait le texte qui
#: explique pourquoi l'ancien était faux — un contrôle trop large rapporte autre
#: chose que ce qu'il prétend mesurer.
DESAVEUX = ("était fausse", "publiée jusqu'ici", "c'est faux", "ne porte pas",
            "ne porte PAS")


def _chaines_publiees(module):
    """Toutes les chaînes littérales du module SAUF les docstrings.

    Une docstring ne va nulle part : `inspect.getsource` n'apparaît que dans
    des fichiers de test, aucun livrable n'en publie. Les inclure ferait
    échouer le contrôle sur la documentation qui explique le défaut.
    """
    arbre = ast.parse(inspect.getsource(module))
    docstrings = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            corps = getattr(noeud, 'body', None) or []
            if (corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)
                    and isinstance(corps[0].value.value, str)):
                docstrings.add(id(corps[0].value))
    return [n.value for n in ast.walk(arbre)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings]


class G1_Aucune_Faussete_N_Est_Publiee(unittest.TestCase):
    """⚠️ LE CONTRÔLE PORTE SUR LA SOURCE, PAS SUR UN TRIANGLE. Un test qui
    n'exercerait que les branches atteintes par mes triangles laisserait
    revenir la phrase dans une branche LoB que je n'ai pas jouée — et c'est
    exactement là que la trace en a trouvé quatre."""

    def test_ni_n2_ni_n5_ne_publient_une_forme_interdite(self):
        for module in (_n2h, _n5c):
            for chaine in _chaines_publiees(module):
                if any(d in chaine for d in DESAVEUX):
                    continue
                for forme in INTERDITES:
                    self.assertNotIn(
                        forme, chaine,
                        f"{module.__name__} publie encore « {forme} » "
                        f"dans : {chaine[:120]}")
        print('    OK G1-1 aucune forme interdite dans les chaines publiees')

    def test_le_desaveu_reste_possible(self):
        # ⚠️ SANS CETTE ÉPREUVE, LE CONTRÔLE PRÉCÉDENT POURRAIT ÊTRE VIDE DE
        # SENS s'il refusait tout. Le texte qui explique le défaut doit passer.
        temoin = ("la justification publiée jusqu'ici (« volume_weighted "
                  "favorise les années récentes ») était fausse")
        self.assertTrue(any(d in temoin for d in DESAVEUX))
        print('    OK G1-2 une phrase qui desavoue la faussete passe')


#: ⚠️ `_h1` EXIGE DEUX COLONNES CONSÉCUTIVES À ≥ 4 FACTEURS — il faut donc un
#: triangle d'au moins 7 années, et `LONG` (5×5) tombait sur le chemin « non
#: testable ». Les deux graines ci-dessous ont été CHOISIES PAR BALAYAGE pour
#: atteindre les deux branches publiantes ; elles sont figées, et le triangle
#: est reconstruit à l'identique à chaque exécution.
_CADENCE = (1.45, 1.14, 1.06, 1.03, 1.015, 1.008, 1.004, 1.002, 1.001)


def _triangle(n, graine):
    """Triangle cumulé déterministe de taille n, bruit gaussien à 2 %."""
    rng = np.random.default_rng(graine)
    C = np.zeros((n, n))
    for i in range(n):
        C[i, 0] = 1000.0 * (1.0 + 0.05 * i)
        for j in range(1, n - i):
            C[i, j] = C[i, j - 1] * _CADENCE[j - 1] * (1.0 + rng.normal(0, 0.02))
    return C


#: H1 VALIDÉE, zéro paire significative — la branche qui portait MA phrase d'A1.
H1_VALIDE = _triangle(9, 11)
#: H1 REJETÉE — la branche qui portait « comportement systématiquement
#: différent », la phrase que `n2_hypotheses` qualifie lui-même de fausse.
H1_REJETE = _triangle(9, 7)


class H1_H1_Dit_Ce_Qu_Il_Teste(unittest.TestCase):
    """⚠️ LE TEST CORRÈLE DES COLONNES, IL NE JUGE PAS LES ANNÉES."""

    def test_les_deux_branches_sont_bien_atteintes(self):
        # ⚠️ SANS CETTE ÉPREUVE, LES SUIVANTES POURRAIENT PASSER À VIDE sur un
        # triangle retombé en « non testable ». C'est le piège qui a fait
        # échouer la première version de ce filet.
        a = HypothesesValidator().valider(H1_VALIDE, lob=LOB)['h1_independance']
        b = HypothesesValidator().valider(H1_REJETE, lob=LOB)['h1_independance']
        self.assertTrue(a['ok']);  self.assertEqual(a['n_colonnes_sig'], 0)
        self.assertFalse(b['ok']); self.assertGreater(b['n_colonnes_testees'], 0)
        print('    OK H1-1 les branches VALIDEE et REJETEE sont atteintes')

    def test_le_message_valide_nomme_la_bonne_grandeur(self):
        h1 = HypothesesValidator().valider(H1_VALIDE, lob=LOB)['h1_independance']
        self.assertIn('colonnes consécutives', h1['message'])
        self.assertIn('CLM-H1', h1['message'])
        self.assertNotIn('années de survenance sont indépendantes',
                         h1['message'])
        print('    OK H1-2 le message nomme les colonnes et renvoie a CLM-H1')

    def test_le_message_tient_sous_la_troncature(self):
        msg = HypothesesValidator().valider(
            H1_VALIDE, lob=LOB)['h1_independance']['message']
        self.assertLessEqual(len(msg), TRONCATURE,
                             f'message de {len(msg)} car., tronque a 200')
        print(f'    OK H1-3 le message de H1 tient en {len(msg)} car.')

    def test_la_narration_validee_renvoie_a_clm_h1(self):
        txt = _texte(H1_VALIDE)
        self.assertIn('CLM-H1', txt)
        self.assertNotIn('les années de survenance se développent', txt)
        print('    OK H1-4 la narration VALIDEE distingue les deux hypotheses')

    def test_la_narration_rejetee_ne_juge_plus_les_annees(self):
        txt = _texte(H1_REJETE)
        self.assertNotIn('systématiquement différent des autres', txt)
        self.assertIn('période de développement', txt)
        print('    OK H1-5 la narration REJETEE ne juge plus les annees')


class I1_Le_Verdict_De_H1_Ne_Bouge_Pas(unittest.TestCase):
    """⚠️ MÊME VERROU QU'EN A1 : le texte change, la décision non."""

    def test_ok_score_et_corr_suivent_la_regle_d_avant(self):
        for C in (H1_VALIDE, H1_REJETE):
            h1 = HypothesesValidator().valider(C, lob=LOB)['h1_independance']
            self.assertEqual(h1['score'],
                             max(0, int((1 - h1['corr_moy']) * 100)))
            self.assertEqual(h1['ok'],
                             h1['corr_moy'] < h1['seuil_utilise']
                             and h1['n_colonnes_sig'] <= 2)
        print('    OK I1-1 ok, score et corr_moy suivent la regle d avant')


if __name__ == '__main__':
    unittest.main(verbosity=2)
