"""
Sceau — trois méthodes de provisionnement doivent rendre trois résultats.

CE QUE CE SCEAU DÉFEND (D08, D09, D10, D11)

D08 — `int()` tronquait vers zéro une ESPÉRANCE de nombre d'invalides.
      Mesuré : PM Rentes IP = **0 EUR jusqu'à 496 assurés, puis 482 895 EUR au
      497e**. L'asymétrie avec `_psap_ip`, qui plancher à 1 sur la même
      quantité, montrait qu'un des deux était faux.

D09 — sans primes exogènes, l'a priori du Bornhuetter-Ferguson valait
      `ult_cl × lr`, l'ultime projeté par Chain Ladder de l'année même qu'on
      cherche à estimer. Mesuré : **BF / CL = 0,680000 exactement**, soit le
      loss ratio a priori — quelle que soit la cadence du triangle.
      Et **Mack − CL = 0,000000** : c'est mathématiquement NORMAL, la réserve
      centrale de Mack EST celle du Chain Ladder. Le défaut n'est pas là ; il
      est d'avoir compté Mack comme une estimation indépendante dans un
      « CV inter-méthodes » de 16,89 %, présenté comme une incertitude de
      modèle et lu comme telle.

D10 — `ra = 0,35 × BE × 0,06 = 2,10 %`, comparé à un plancher de 3,00 % : le
      `max` retournait le plancher pour TOUTE valeur de BE. Le coût du capital
      n'avait aucun effet, et l'étiquette publiée annonçait « CoC 6 % ».

D11 — le sigma de PRIMES était appliqué au Best Estimate. Le Règlement délégué
      (UE) 2015/35 définit deux mesures de volume distinctes : `V(prem,s) =
      max(Ps ; P(last,s)) + FP(existing) + FP(future)` (art. 147 §3) et
      `V(res,s)` = meilleure estimation des sinistres à payer (art. 147 §6).
      Le BE était compté deux fois et l'exposition aux primes était absente.
"""
import contextlib
import io
import unittest

import numpy as np

from .prevoyance.p3_provisionnement.agent import (
    RA_PLANCHER_PCT, SIGMA_NSLT_PRIMES, SIGMA_NSLT_RESERVES,
    AgentP3ProvissionnementPrevoyance,
)


def _p1(nb=500):
    return {"success": True, "primes_acquises": 340_830.0, "nb_assures": nb,
            "salaire_brut": 45_000.0, "taux_cotisation_pct": 1.51,
            "taux_rente_ipp": 0.60}


def _p2(nb=500):
    return {"success": True, "sorties_p3": {
        "age": 40.0, "taux_ip": 0.00336, "taux_itt": 0.042,
        "prob_maintien_6m": 0.578, "prob_maintien_12m": 0.345,
        "prob_maintien_24m": 0.145, "esperance_duree_ip": 24.8,
        "salaire_brut": 45_000.0, "taux_rente_ipp": 0.60,
        "primes_acquises": 340_830.0, "nb_assures": nb, "franchise_jours": 90}}


def _run(nb=500, triangle=None):
    with contextlib.redirect_stdout(io.StringIO()):
        return AgentP3ProvissionnementPrevoyance(verbose=False).run(
            result_p1=_p1(nb), result_p2=_p2(nb), triangle_itt=triangle,
            generer_graphiques=False)


# Trois cadences DIFFERENTES -- et non trois homotheties du meme triangle :
# une homothetie multiplie CL et BF dans le meme rapport et ne prouve rien.
TRIANGLES = {
    "cadence lente": np.array([
        [50e3, 110e3, 150e3, 164e3, 170e3], [55e3, 120e3, 163e3, 178e3, 0],
        [52e3, 114e3, 155e3, 0, 0], [58e3, 127e3, 0, 0, 0], [54e3, 0, 0, 0, 0]]),
    "cadence rapide": np.array([
        [140e3, 160e3, 165e3, 166e3, 166e3], [150e3, 172e3, 177e3, 178e3, 0],
        [145e3, 166e3, 171e3, 0, 0], [155e3, 178e3, 0, 0, 0], [148e3, 0, 0, 0, 0]]),
    "derniere annee forte": np.array([
        [85e3, 138e3, 155e3, 162e3, 165e3], [92e3, 148e3, 166e3, 174e3, 0],
        [88e3, 142e3, 160e3, 0, 0], [95e3, 153e3, 0, 0, 0], [180e3, 0, 0, 0, 0]]),
}


class TestLaPmDeRentesEstContinue(unittest.TestCase):
    """D08 — un assuré de plus ne fait pas apparaître un demi-million."""

    def test_aucun_saut_entre_496_et_497_assures(self):
        avant = _run(nb=496)["pm_rentes_ip"]
        apres = _run(nb=497)["pm_rentes_ip"]
        self.assertGreater(avant, 0.0,
                           "A 496 assures la PM vaut %.2f : la troncature est "
                           "revenue." % avant)
        saut = abs(apres - avant) / max(avant, 1e-9)
        self.assertLess(
            saut, 0.01,
            "Saut de %.1f %% entre 496 et 497 assures (%.0f -> %.0f). Avant "
            "correction : 0 EUR puis 482 895 EUR." % (saut * 100, avant, apres))

    def test_la_pm_croit_avec_l_effectif(self):
        valeurs = [_run(nb=n)["pm_rentes_ip"] for n in (100, 400, 1000)]
        self.assertEqual(valeurs, sorted(valeurs))
        self.assertTrue(all(v > 0 for v in valeurs))


class TestLeBfEstIndependantDuChainLadder(unittest.TestCase):
    """D09 — un BF qui vaut toujours lr × CL n'est pas une seconde méthode."""

    def test_le_rapport_bf_sur_cl_varie_avec_la_cadence(self):
        rapports = {}
        for nom, triangle in TRIANGLES.items():
            resultat = _run(triangle=triangle)
            cl = float(resultat["chain_ladder"]["reserve_totale"])
            bf = float(resultat["bf"]["reserve_totale"])
            rapports[nom] = round(bf / max(cl, 1e-9), 4)
        self.assertGreater(
            len(set(rapports.values())), 1,
            "BF / CL est CONSTANT sur trois cadences differentes : %s. "
            "C'est la signature de la degenerescence — avant correction, il "
            "valait 0,680000, soit exactement le loss ratio a priori."
            % rapports)

    def test_le_bf_publie_la_provenance_de_son_a_priori(self):
        resultat = _run(triangle=TRIANGLES["cadence lente"])
        source = resultat["bf"].get("source_apriori") or \
            resultat["bf"].get("source_lr")
        self.assertTrue(
            source, "Le BF doit dire d'ou vient son a priori : primes "
                    "exogenes, ou volume des annees matures.")


class TestLeCvInterMethodesNeCompteQueDesMethodesDistinctes(unittest.TestCase):
    """D09 — la réserve centrale de Mack EST celle du Chain Ladder."""

    def test_mack_est_exclu_du_cv_et_l_exclusion_est_declaree(self):
        detail = _run(triangle=TRIANGLES["cadence lente"]).get("be_itt_detail", {})
        exclues = detail.get("cv_inter_exclues")
        self.assertIn(
            "mack_1993", exclues or [],
            "Mack doit etre exclu du CV inter-methodes : sa reserve centrale "
            "est celle du Chain Ladder (ecart mesure : 0,000000). Exclues : %r"
            % exclues)
        base = detail.get("cv_inter_methodes") or []
        self.assertNotIn("mack_1993", base)
        self.assertGreaterEqual(
            len(base), 2,
            "Le CV doit porter sur au moins deux methodes distinctes ; base "
            "publiee : %r" % base)

    def test_la_base_du_cv_est_publiee(self):
        detail = _run(triangle=TRIANGLES["cadence lente"]).get("be_itt_detail", {})
        self.assertIn("cv_inter_methodes", detail,
                      "Un CV qui ne dit pas sur quoi il porte ne se verifie pas.")


class TestLeRiskAdjustmentDitQuelTermeLemporte(unittest.TestCase):
    """D10 — le plancher mordait toujours, et l'étiquette annonçait le CoC."""

    def test_le_ra_publie_le_terme_effectivement_retenu(self):
        resultat = _run()
        source = resultat.get("source_ra") or \
            resultat.get("sorties_p4", {}).get("source_ra")
        self.assertTrue(
            source, "Le Risk Adjustment doit dire lequel de ses deux termes "
                    "l'emporte : le cout du capital ou le plancher.")
        ra = float(resultat["risk_adjustment"])
        be = float(resultat["be_prevoyance"])
        if abs(ra / max(be, 1e-9) - RA_PLANCHER_PCT) < 1e-6:
            self.assertIn(
                "PLANCHER", source.upper(),
                "Le RA vaut exactement le plancher mais l'etiquette ne le dit "
                "pas : %r" % source)


class TestLeScrDePrimePorteSurDesPrimes(unittest.TestCase):
    """D11 — art. 147 §3 : la mesure de volume des primes ne contient pas le BE."""

    def test_le_scr_de_prime_utilise_le_volume_de_primes(self):
        resultat = _run()
        scr = resultat["scr"]
        self.assertGreater(
            float(scr["volume_primes"]), 0.0,
            "Le SCR de prime doit porter sur un volume de PRIMES.")
        attendu = 3.0 * SIGMA_NSLT_PRIMES * float(scr["volume_primes"])
        self.assertAlmostEqual(
            attendu, float(scr["scr_primes"]), delta=1.0,
            msg="SCR de prime = %.0f ; attendu 3 x sigma x volume de primes "
                "= %.0f. Avant correction, l'assiette etait le BE."
                % (float(scr["scr_primes"]), attendu))

    def test_les_sigmas_sont_ceux_du_segment_2_de_l_annexe_xiv(self):
        """Assurance de protection du revenu : 8,5 % primes, 14 % réserves."""
        self.assertAlmostEqual(0.085, SIGMA_NSLT_PRIMES, places=4)
        self.assertAlmostEqual(0.14, SIGMA_NSLT_RESERVES, places=4)

    def test_le_be_n_est_plus_compte_deux_fois(self):
        """Doubler les primes sans toucher au BE doit changer le SCR de prime."""
        with contextlib.redirect_stdout(io.StringIO()):
            agent = AgentP3ProvissionnementPrevoyance(verbose=False)
            p1_double = _p1()
            p1_double["primes_acquises"] *= 2
            double = agent.run(result_p1=p1_double, result_p2=_p2(),
                               generer_graphiques=False)
        simple = _run()
        self.assertGreater(
            float(double["scr"]["scr_primes"]),
            float(simple["scr"]["scr_primes"]),
            "Doubler les primes ne change pas le SCR de prime : l'exposition "
            "aux primes est encore absente du calcul.")


if __name__ == "__main__":
    unittest.main()
