# -*- coding: utf-8 -*-
"""
=============================================================================
 A7 Ibrahim — le fil de la courbe des taux est branché, et le reste
=============================================================================

 ⚠️ POURQUOI CE FICHIER EXISTE : LE DÉFAUT A SURVÉCU PARCE QUE RIEN NE
 L'EXERÇAIT.

 `run(courbe_rfr=…)` acheminait la courbe de l'actuaire jusqu'à
 `_calculer_risk_margin`, qui la recevait en paramètre et NE LA LISAIT
 JAMAIS : elle appelait `get_taux_rfr`, c'est-à-dire la courbe EMBARQUÉE en
 dur. Mesuré avant correctif — sur GenIns, une courbe plate à 0,5 %, à 10 %
 et à 25 % rendaient TOUTES une Risk Margin de 2 240 584 €, au centime. Tout
 le mécanisme d'apport — l'import du fichier EIOPA officiel, le taux assumé,
 les deux boutons de l'application — était un no-op silencieux.

 Le rapport publiait par-dessus `DATE_COURBE`, celle de l'embarquée, quoi
 qu'il arrive : un actuaire important la courbe en vigueur lisait
 « 2025-03-31 ». Soit il le remarquait et perdait confiance dans l'outil,
 soit il ne le remarquait pas et signait un bilan qu'il croyait corrigé.

 AUCUN TEST NE FOURNISSAIT UNE AUTRE COURBE QUE LA COURBE PAR DÉFAUT. C'est
 la seule raison pour laquelle le défaut a tenu : le chemin nominal, celui
 que tout le monde emprunte, donne le même résultat qu'il soit branché ou
 non. C'est ce trou-là que ce fichier ferme, et non seulement le bug.

 ⚠️ ET UN OUTIL DE PROPRETÉ A FAILLI FAIRE CIMENTER LE DÉFAUT. `vulture`
 voyait `courbe` comme une variable morte, à 100 % de confiance, et c'était
 littéralement exact. Le retirer aurait effacé jusqu'à la trace qu'une courbe
 était censée arriver là. Un paramètre mort et un fil débranché se
 ressemblent dans un outil et s'opposent dans le code.
=============================================================================
"""

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement)
from direction_non_vie.provisionnement.a7_provisionnement.config.rfr_eiopa import (
    DATE_COURBE, get_courbe_embarquee, get_courbe_taux_plat, get_taux_rfr)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS)

_CACHE = {}


def _run(courbe=None, cle=None):
    """Un run A7, mis en cache par clé — l'agent est cher."""
    if cle is not None and cle in _CACHE:
        return _CACHE[cle]
    r = AgentA7Provisionnement(verbose=False).run(
        source=np.asarray(GENINS, dtype=float), mode_declare='cumule',
        generer_graphiques=False, generer_word=False, n_sim_bootstrap=60,
        seed=42, courbe_rfr=courbe)
    if cle is not None:
        _CACHE[cle] = r
    return r


# =============================================================================
#  T1 — LE VERROU ANTI-RÉCIDIVE
# =============================================================================

class T1_Deux_Courbes_Deux_Risk_Margins(unittest.TestCase):
    """⚠️ LE VERROU QUI COMPTE : le no-op ne peut plus revenir."""

    def test_deux_courbes_differentes_donnent_deux_risk_margins(self):
        """L'assertion exacte qui échouait avant le correctif."""
        rm = {}
        for taux in (0.5, 5.0, 25.0):
            r = _run(get_courbe_taux_plat(taux), cle='plat_%s' % taux)
            rm[taux] = float(r['n4']['risk_margin'])
        self.assertEqual(len(set(rm.values())), 3,
                         'des courbes différentes rendent la MÊME Risk Margin '
                         '— la courbe est de nouveau ignorée : %s' % rm)
        ecart = abs(rm[25.0] / rm[0.5] - 1) * 100
        self.assertGreater(ecart, 20,
                           'une courbe à 25 %% et une à 0,5 %% ne déplacent '
                           'que %.1f %% de la Risk Margin' % ecart)
        print('    OK RFR-1 3 courbes → 3 Risk Margins : %s — écart 0,5 %% vs '
              '25 %% = %.1f %%'
              % (' / '.join('%.0f€' % v for v in rm.values()), ecart))

    def test_la_fonction_de_taux_de_la_courbe_est_reellement_appelee(self):
        """Un écart pourrait venir d'ailleurs — ici on compte les appels.

        Une courbe espionne rend un taux constant ET note chaque appel. Si le
        compteur reste à zéro, la Risk Margin a été calculée sur autre chose.
        """
        appels = []

        def _espion(t):
            appels.append(float(t))
            return 0.04

        courbe = dict(get_courbe_taux_plat(4.0))
        courbe['taux_fn'] = _espion
        _run(courbe)
        self.assertGreater(len(appels), 3,
                           "la fonction de taux de la courbe n'a pas été "
                           "appelée : elle est de nouveau contournée")
        self.assertEqual(sorted(appels), sorted(set(appels)),
                         'une maturité est actualisée deux fois')
        self.assertGreaterEqual(min(appels), 1.0,
                                'une maturité inférieure à 1 an est demandée')
        print('    OK RFR-2 la fonction de taux est appelée %d fois, '
              'maturités %.0f à %.0f ans'
              % (len(appels), min(appels), max(appels)))

    def test_un_taux_plus_eleve_actualise_davantage(self):
        """Garde-fou de SENS : actualiser plus fort donne une RM plus petite.

        Un test qui vérifierait seulement « ça bouge » passerait avec un signe
        inversé. Celui-ci ne passerait pas.
        """
        rm = [float(_run(get_courbe_taux_plat(t), cle='plat_%s' % t)
                    ['n4']['risk_margin'])
              for t in (0.5, 5.0, 25.0)]
        self.assertEqual(rm, sorted(rm, reverse=True),
                         'la Risk Margin ne décroît pas quand les taux '
                         'montent : le facteur d\'actualisation est inversé')
        print('    OK RFR-3 RM décroissante avec le taux : %s'
              % ' > '.join('%.0f€' % v for v in rm))


# =============================================================================
#  T2 — LE RAPPORT DÉCRIT LA COURBE RÉELLEMENT EMPLOYÉE
# =============================================================================

class T2_La_Date_Suit_La_Courbe(unittest.TestCase):

    def test_la_courbe_embarquee_publie_sa_date_et_sa_peremption(self):
        n4 = _run(None, cle='defaut')['n4']
        self.assertEqual(n4.get('date_courbe_rfr'), DATE_COURBE)
        self.assertEqual((n4.get('peremption_courbe') or {}).get('statut'),
                         'ROUGE',
                         'la courbe embarquée n\'est plus jugée périmée — '
                         'a-t-elle été mise à jour ? le seuil a-t-il bougé ?')
        print('    OK RFR-4 courbe embarquée : date %s publiée, péremption '
              'ROUGE' % DATE_COURBE)

    def test_une_courbe_fournie_publie_la_sienne_et_non_l_embarquee(self):
        """⚠️ LE DÉFAUT LE PLUS TROMPEUR DES DEUX.

        Un actuaire important la courbe EIOPA en vigueur lisait « 2025-03-31 »
        dans son rapport. Le chiffre était faux ET la date le cachait.
        """
        n4 = _run(get_courbe_taux_plat(3.0), cle='plat_3.0')['n4']
        self.assertNotEqual(n4.get('date_courbe_rfr'), DATE_COURBE,
                            'le rapport publie encore la date de la courbe '
                            'EMBARQUÉE alors qu\'une autre a servi')
        self.assertIn('3.000', str(n4.get('source_courbe_rfr') or ''),
                      'la source publiée ne décrit pas la courbe employée')
        print('    OK RFR-5 courbe fournie : date « %s », source « %s »'
              % (n4.get('date_courbe_rfr'),
                 str(n4.get('source_courbe_rfr'))[:52]))

    def test_une_courbe_fournie_n_est_pas_declaree_a_jour(self):
        """Le module ne connaît pas sa date : il ne peut pas la juger VERTE.

        Affirmer VERT sur une courbe dont on ignore l'arrêté serait inventer
        un verdict — c'est la règle posée au lot BFCC.
        """
        per = (_run(get_courbe_taux_plat(3.0), cle='plat_3.0')['n4']
               .get('peremption_courbe') or {})
        self.assertEqual(per.get('statut'), 'NON TESTABLE')
        self.assertIn('actuaire', str(per.get('message', '')).lower())
        print('    OK RFR-6 courbe fournie : péremption NON TESTABLE, et le '
              'message dit pourquoi')

    def test_un_import_rate_retombe_sur_l_embarquee_ET_sur_son_diagnostic(self):
        """⚠️ LE CAS SUBTIL, ET IL EST RÉEL.

        Quand l'import Excel échoue, `get_courbe_depuis_excel` se rabat sur
        `get_taux_rfr` : la courbe EFFECTIVEMENT appliquée est l'embarquée.
        Publier « NON TESTABLE » là reviendrait à taire une courbe périmée
        derrière un import raté.
        """
        from direction_non_vie.provisionnement.a7_provisionnement.config \
            .rfr_eiopa import get_courbe_depuis_excel
        courbe = get_courbe_depuis_excel(b'ceci n est pas un fichier excel')
        self.assertEqual(courbe['type'], 'erreur')
        n4 = _run(courbe)['n4']
        self.assertEqual(n4.get('date_courbe_rfr'), DATE_COURBE)
        self.assertEqual((n4.get('peremption_courbe') or {}).get('statut'),
                         'ROUGE',
                         'un import raté masque la péremption de la courbe '
                         'qui sert réellement')
        self.assertAlmostEqual(float(n4['risk_margin']),
                               float(_run(None, cle='defaut')
                                     ['n4']['risk_margin']), places=2)
        print('    OK RFR-7 import raté → courbe embarquée, sa péremption '
              'ROUGE, et la même Risk Margin')


# =============================================================================
#  T3 — LE CHEMIN PAR DÉFAUT N'A PAS BOUGÉ
# =============================================================================

class T3_Le_Defaut_Est_Inchange(unittest.TestCase):

    def test_aucune_courbe_et_courbe_embarquee_donnent_le_meme_euro(self):
        """Le correctif ne déplace rien sur le chemin que tout le monde suit."""
        sans = _run(None, cle='defaut')['n4']
        avec = _run(get_courbe_embarquee(), cle='embarquee_explicite')['n4']
        for cle in ('risk_margin', 'provisions_techniques_s2', 'ratio_rm_be',
                    'best_estimate'):
            self.assertAlmostEqual(float(sans[cle]), float(avec[cle]),
                                   places=2, msg='divergence sur %r' % cle)
        print('    OK RFR-8 courbe implicite == courbe embarquée explicite, '
              'au centime')

    def test_le_taux_lu_est_bien_celui_du_module_pour_l_embarquee(self):
        """La table de run-off doit porter les taux de la courbe embarquée."""
        tableau = (_run(None, cle='defaut')['n4'].get('tableau_run_off')
                   or [])
        self.assertTrue(tableau, 'tableau de run-off vide')
        for ligne in tableau:
            attendu = round(get_taux_rfr(int(ligne['annee']) + 1) * 100, 4)
            self.assertAlmostEqual(float(ligne['taux_rfr']), attendu, places=4,
                                   msg='année %s' % ligne['annee'])
        print('    OK RFR-9 les %d taux de la table de run-off == la courbe '
              'embarquée' % len(tableau))



# =============================================================================
#  T4 — UNE COURBE PÉRIMÉE PLAFONNE LE STATUT
# =============================================================================

def _triangle_regulier(n=8, f=(1.60, 1.25, 1.12, 1.06, 1.03, 1.015, 1.005)):
    """Un triangle assez régulier pour sortir VERT — et il a fallu le CONSTRUIRE.

    ⚠️ AUCUN DES CINQ TRIANGLES DE RÉFÉRENCE NE SORT VERT : mesuré, les dix
    exécutions (cinq triangles × avec et sans exposition) rendent ROUGE ou
    AMBRE, pour d'autres raisons — méthode unique, filet de sécurité,
    dispersion. Un verrou posé sur eux ne prouverait donc RIEN du
    plafonnement : il resterait vert quoi qu'on fasse à la courbe.

    D'où ce triangle, dont l'exposition est calée sur l'ultime réel pour que
    Chain Ladder, Bornhuetter-Ferguson et Cape Cod convergent — `cv_inter`
    tombe à 0,0 et le statut est VERT tant que la courbe l'est.
    """
    plein = np.zeros((n, n))
    for i in range(n):
        v = 1_000_000.0 * (1 + 0.02 * i)
        plein[i, 0] = v
        for j in range(1, n):
            v *= f[j - 1] if j - 1 < len(f) else 1.0
            plein[i, j] = v
    C = plein.copy()
    for i in range(n):
        for j in range(n - i, n):
            C[i, j] = 0.0
    return C, plein[:, -1]


class T4_Une_Courbe_Perimee_Plafonne_Le_Statut(unittest.TestCase):
    """⚠️ ET CE PLAFONNEMENT N'AURAIT PAS EU DE SENS AVANT QUE LE FIL SOIT
    BRANCHÉ : refuser le VERT sans laisser aucun moyen de le regagner aurait
    puni sans offrir de remède. On sanctionne une situation qui a désormais
    une réponse — importer le fichier EIOPA, ou assumer un taux.
    """

    def _statut(self, date_courbe):
        import direction_non_vie.provisionnement.a7_provisionnement.config \
            .rfr_eiopa as RFR
        C, ult = _triangle_regulier()
        origine = RFR.DATE_COURBE
        RFR.DATE_COURBE = date_courbe
        try:
            r = AgentA7Provisionnement(verbose=False).run(
                source=C, mode_declare='cumule', generer_graphiques=False,
                generer_word=False, n_sim_bootstrap=60, seed=42, primes=ult)
        finally:
            RFR.DATE_COURBE = origine
        n4 = r['n4']
        return (n4['statut'],
                (n4.get('peremption_courbe') or {}).get('statut'),
                float(n4['best_estimate']), float(n4['risk_margin']))

    def test_une_courbe_fraiche_laisse_le_vert(self):
        """Le témoin : sans lui, le test suivant ne prouverait rien."""
        import datetime
        statut, per, _, _ = self._statut(datetime.date.today().isoformat())
        self.assertEqual(per, 'VERT')
        self.assertEqual(statut, 'VERT',
                         'ce scénario ne sort plus VERT même avec une courbe '
                         'fraîche — le verrou suivant ne prouverait plus rien')
        print('    OK RFR-10 courbe fraîche → péremption VERT, statut VERT')

    def test_une_courbe_rouge_plafonne_le_vert_a_ambre(self):
        """Le verrou du lot : un VERT ne peut pas coexister avec une courbe
        périmée d'un an."""
        import datetime
        vieille = (datetime.date.today()
                   - datetime.timedelta(days=500)).isoformat()
        statut, per, _, _ = self._statut(vieille)
        self.assertEqual(per, 'ROUGE')
        self.assertEqual(statut, 'AMBRE',
                         'une courbe ROUGE ne plafonne plus le statut')
        print('    OK RFR-11 courbe de 16 mois → péremption ROUGE, statut '
              'plafonné à AMBRE')

    def test_une_courbe_ambre_ne_plafonne_pas(self):
        """⚠️ SEUL LE ROUGE PLAFONNE, ET C'EST DÉLIBÉRÉ.

        Le module le dit lui-même : un trimestre de retard reste usuel entre
        deux arrêtés, un an ne l'est pas. Faire plafonner l'AMBRE reviendrait à
        interdire le VERT presque toute l'année, et un plafonnement permanent
        ne veut plus rien dire.
        """
        import datetime
        six_mois = (datetime.date.today()
                    - datetime.timedelta(days=183)).isoformat()
        statut, per, _, _ = self._statut(six_mois)
        self.assertEqual(per, 'AMBRE')
        self.assertEqual(statut, 'VERT',
                         'une courbe AMBRE plafonne le statut : le seuil de '
                         'plafonnement a glissé du ROUGE vers l\'AMBRE')
        print('    OK RFR-12 courbe de 6 mois → péremption AMBRE, statut VERT '
              'conservé')

    def test_le_plafonnement_deplace_un_verdict_et_pas_un_euro(self):
        """La courbe n'entre pas dans le Best Estimate : elle actualise la
        Risk Margin, et le DIAGNOSTIC ne touche ni l'un ni l'autre."""
        import datetime
        frais = self._statut(datetime.date.today().isoformat())
        vieux = self._statut((datetime.date.today()
                              - datetime.timedelta(days=500)).isoformat())
        self.assertNotEqual(frais[0], vieux[0], 'le statut n\'a pas bougé')
        self.assertAlmostEqual(frais[2], vieux[2], places=2,
                               msg='le Best Estimate a bougé')
        self.assertAlmostEqual(frais[3], vieux[3], places=2,
                               msg='la Risk Margin a bougé : seule la DATE de '
                                   'la courbe change, pas ses taux')
        print('    OK RFR-13 statut %s → %s, BE et RM identiques au centime'
              % (frais[0], vieux[0]))

if __name__ == '__main__':
    unittest.main(verbosity=2)
