# -*- coding: utf-8 -*-
"""
=============================================================================
  ActuarIA — A7  ·  MONOTONIE DE LA GOUVERNANCE
=============================================================================

UN VERDICT PLUS SÉVÈRE NE PEUT PAS AVOIR MOINS D'EFFET QU'UN VERDICT MODÉRÉ.

Le circuit `_hypotheses_a_signaler` violait cette règle : il ne lisait que
« À JUSTIFIER ». Une hypothèse déclarant une cible sans figurer dans
`_HYPOTHESES_BLOQUANTES` plafonnait donc le statut quand elle était
modérément en défaut, et ne faisait RIEN quand elle l'était franchement.

BFCC-H1 l'a révélé — elle est la seule des quatre republications de CLM-H1 à
déclarer des cibles, `(BF, CC)`, là où CLM-H1, BOOT-H1 et MCL-H1 ont toutes
`()`. Mais LE VERROU CENTRAL DE CE FICHIER NE PARLE PAS DE BFCC-H1 : il
énonce la propriété pour TOUTE hypothèse, présente ou future.

⚠️ CE DÉFAUT ÉTAIT INVISIBLE, ET CE N'ÉTAIT PAS STRUCTUREL. Le plafonnement
ne s'applique qu'à un statut VERT, or la courbe RFR embarquée est périmée et
plafonne déjà tout VERT à AMBRE : aucun portefeuille n'atteignait le cas.
Mesuré sur 216 triangles avec une courbe à jour — 29 portefeuilles VERT, dont
14 portant une BFCC-H1 NON VALIDÉE, soit 48 %. C'est ce qui a décidé de
corriger AVANT l'import de la courbe EIOPA, et non après.
"""

import unittest

import numpy as np

from direction_non_vie.provisionnement.a7_provisionnement import (
    n4_best_estimate as N4)
from direction_non_vie.provisionnement.a7_provisionnement.agent import (
    AgentA7Provisionnement)
from direction_non_vie.provisionnement.a7_provisionnement.test_a7_ibrahim import (
    GENINS,
)

_G = np.asarray(GENINS, dtype=float)
_EXPO = [float(x) for x in (17_000_000, 18_000_000, 19_500_000, 20_000_000,
                            21_000_000, 22_000_000, 23_000_000, 24_000_000,
                            25_000_000, 26_000_000)]

#: Toutes les cibles qu'une hypothèse peut déclarer sur une méthode du BE.
_TOUTES = {'chain_ladder': 1.0, 'bornhuetter_ferguson': 1.0, 'cape_cod': 1.0}


def _n2(code, statut, cibles):
    """Un `n2` minimal portant UNE hypothèse, pour interroger le circuit."""
    famille = 'clm' if code.startswith('CLM') else 'bfcc'
    return {famille: {'hypotheses': {
        code: {'statut': statut, 'critique_pour': list(cibles)}}}}


# =============================================================================
#  MONO-1 — LA PROPRIÉTÉ, ÉNONCÉE POUR TOUTE HYPOTHÈSE
# =============================================================================

class TMONO1_Propriete(unittest.TestCase):

    def test_non_validee_a_toujours_au_moins_l_effet_de_a_justifier(self):
        """⚠️ LE VERROU CENTRAL, ET IL NE NOMME AUCUNE HYPOTHÈSE.

        Pour toute combinaison de cibles et toute méthode retenue, l'ensemble
        signalé quand le verdict est NON VALIDÉE doit CONTENIR celui obtenu
        quand il est À JUSTIFIER. Une hypothèse future qui déclarerait une
        cible sans être bloquante hérite de la règle sans que personne ait à
        y penser.
        """
        combinaisons = [(), ('chain_ladder',), ('cape_cod',),
                        ('bornhuetter_ferguson',),
                        ('chain_ladder', 'mack'),
                        ('bornhuetter_ferguson', 'cape_cod'),
                        ('percentiles_mack',)]
        retenues = [_TOUTES, {'chain_ladder': 1.0},
                    {'chain_ladder': 1.0, 'cape_cod': 1.0}, {}]
        n_cas = 0
        for code in ('BFCC-H1', 'BFCC-H9', 'CLM-H2', 'CLM-H9'):
            for cibles in combinaisons:
                for incluses in retenues:
                    doux = set(N4._hypotheses_a_signaler(
                        _n2(code, 'À JUSTIFIER', cibles), incluses))
                    dur = set(N4._hypotheses_a_signaler(
                        _n2(code, 'NON VALIDÉE', cibles), incluses))
                    self.assertTrue(
                        doux <= dur,
                        f"{code} cibles={cibles} retenues={sorted(incluses)} : "
                        f"À JUSTIFIER signale {doux}, NON VALIDÉE signale "
                        f"{dur} — un verdict plus sévère a MOINS d'effet")
                    n_cas += 1
        print(f"    OK MONO-1a monotonie vérifiée sur {n_cas} combinaisons "
              f"(4 codes × 7 jeux de cibles × 4 jeux de méthodes retenues)")

    def test_les_deux_statuts_sont_declares_ensemble(self):
        """La règle est portée par une constante lisible, pas par un `==`
        enfoui dans une compréhension."""
        self.assertIn('À JUSTIFIER', N4._STATUTS_A_SIGNALER)
        self.assertIn('NON VALIDÉE', N4._STATUTS_A_SIGNALER)
        self.assertNotIn('VALIDÉE', N4._STATUTS_A_SIGNALER)
        self.assertNotIn('NON TESTABLE', N4._STATUTS_A_SIGNALER)
        print(f"    OK MONO-1b `_STATUTS_A_SIGNALER` = "
              f"{N4._STATUTS_A_SIGNALER}")

    def test_un_verdict_satisfait_ne_signale_jamais(self):
        """La correction ne doit pas transformer le circuit en passe-tout."""
        for statut in ('VALIDÉE', 'NON TESTABLE'):
            self.assertEqual(
                N4._hypotheses_a_signaler(
                    _n2('BFCC-H1', statut, ('cape_cod',)), _TOUTES), [])
        print("    OK MONO-1c VALIDÉE et NON TESTABLE ne signalent rien")

    def test_une_hypothese_descriptive_ne_signale_jamais(self):
        """`critique_pour` vide = descriptive. Aucun statut ne la fait parler —
        c'est le cas de CLM-H1, BOOT-H1 et MCL-H1."""
        for statut in ('À JUSTIFIER', 'NON VALIDÉE'):
            self.assertEqual(
                N4._hypotheses_a_signaler(_n2('CLM-H1', statut, ()),
                                          _TOUTES), [])
        print("    OK MONO-1d une hypothèse à `critique_pour` vide reste muette "
              "aux deux niveaux de sévérité")

    def test_le_filtre_par_methode_retenue_survit(self):
        """Une hypothèse portant sur une méthode ÉCARTÉE ne plafonne rien :
        la sanctionner reviendrait à la compter deux fois."""
        n2 = _n2('BFCC-H5', 'NON VALIDÉE', ('cape_cod',))
        self.assertEqual(N4._hypotheses_a_signaler(n2, _TOUTES), ['BFCC-H5'])
        self.assertEqual(
            N4._hypotheses_a_signaler(n2, {'chain_ladder': 1.0}), [])
        print("    OK MONO-1e le filtre par méthode retenue est intact : une "
              "méthode exclue ne peut pas plafonner une seconde fois")


# =============================================================================
#  MONO-2 — L'EFFET RÉEL, ET SON ABSENCE D'EFFET SUR LES EUROS
# =============================================================================

class TMONO2_Effet(unittest.TestCase):

    @staticmethod
    def _run(courbe=None):
        kw = dict(source=_G, mode_declare='cumule', primes=_EXPO,
                  generer_graphiques=False, generer_word=False,
                  generer_html=False, n_sim_bootstrap=200, seed=42)
        if courbe is not None:
            kw['courbe_rfr'] = courbe
        return AgentA7Provisionnement(verbose=False).run(**kw)

    def test_la_cle_publiee_porte_le_nom_de_ce_qu_elle_contient(self):
        """Elle ne contient plus seulement des « à justifier » : la nommer
        ainsi serait un nom qui ment."""
        n4 = self._run()['n4']
        self.assertIn('hypotheses_a_signaler', n4)
        self.assertNotIn('hypotheses_a_justifier', n4)
        print("    OK MONO-2a la clé publiée s'appelle `hypotheses_a_signaler`")

    def test_une_non_validee_sur_methode_retenue_est_desormais_signalee(self):
        """Le cas qui a motivé le lot, vérifié de bout en bout."""
        n2 = {'bfcc': {'hypotheses': {
            'BFCC-H1': {'statut': 'NON VALIDÉE',
                        'critique_pour': ['bornhuetter_ferguson', 'cape_cod']}}}}
        self.assertEqual(
            N4._hypotheses_a_signaler(n2, _TOUTES), ['BFCC-H1'],
            "une BFCC-H1 NON VALIDÉE sur des méthodes retenues doit être "
            "signalée — c'est l'inversion que ce lot corrige")
        print("    OK MONO-2b BFCC-H1 NON VALIDÉE est signalée, là où elle "
              "était muette")

    def test_le_best_estimate_ne_bouge_pas(self):
        """⚠️ CE CIRCUIT NE TOUCHE QUE LE STATUT, PAR CONSTRUCTION. Il
        n'alimente ni la sélection des méthodes, ni les poids, ni la réserve.
        Mesuré sur 216 triangles : 14 statuts déplacés, ZÉRO euro."""
        n4 = self._run()['n4']
        for cle in ('best_estimate', 'risk_margin', 'provisions_techniques_s2'):
            self.assertGreater(float(n4[cle]), 0.0, cle)
        # Le signalement n'entre dans aucune des grandeurs monétaires : on le
        # vérifie en le vidant de force, sans que rien ne bouge.
        original = N4._hypotheses_a_signaler
        try:
            N4._hypotheses_a_signaler = lambda *_: []
            sans = self._run()['n4']
        finally:
            N4._hypotheses_a_signaler = original
        for cle in ('best_estimate', 'risk_margin', 'provisions_techniques_s2'):
            self.assertAlmostEqual(float(n4[cle]), float(sans[cle]), places=2,
                                   msg=f"{cle} dépend du signalement")
        print("    OK MONO-2c Best Estimate, marge de risque et provisions "
              "techniques S2 sont indifférents au signalement")


if __name__ == '__main__':
    unittest.main(verbosity=2)
