"""
Sceau — le S/P est un rapport de sinistres à primes, et les primes ont une base.

LA DÉFINITION QUI FAIT FOI
    « Ce ratio, appelé P/C pour prestations sur cotisations ou S/P pour
      sinistres sur primes, rapporte simplement la charge de sinistres au
      montant des cotisations. […] la somme des prestations et des provisions. »
    — V. PAVARD, mémoire ENSAE Paris / Institut des Actuaires, 13/03/2023, p. 30.

CE QUE CE SCEAU DÉFEND (D07, D06, D02)

D07 — P3 construisait `lr = taux_cotisation_pct / 100 × 0,80`. Un pourcentage
      de SALAIRE multiplié par 0,80 n'est pas un rapport de sinistres à primes.
      Mesuré : au taux nominal de 1,51 %, l'agent publiait un **S/P de 1,21 %**,
      et il aurait fallu un taux de cotisation de **125 % du salaire** pour
      atteindre 100 %. L'invariant défendu ici est le plus simple qui soit :
      **le S/P ne doit pas dépendre du taux de cotisation.**

D06 — H5 ne bornait QUE PAR LE HAUT : un S/P de 1,21 % passait donc pour
      validé. La borne BASSE est le vrai correctif.

D02 — la prime IP était divisée par la durée du contrat, pas la prime ITT,
      alors que les deux partent d'un taux d'entrée annuel. Mesuré :
      **1 937,60 € à 1 an contre 96,88 € à 20 ans**, rapport 20,0× exact.

Et une correction de la charge de sinistres en santé : S2 n'y mettait que les
prestations réglées, sans les provisions. Mesuré : **75,6 % → 101,6 %**, soit
**+26,0 points** — le régime passe d'excédentaire à déficitaire.
"""
import contextlib
import io
import unittest

import numpy as np

from .prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
from .prevoyance.p3_provisionnement.agent import AgentP3ProvissionnementPrevoyance
from .sante.s1_tarification.agent import AgentS1TarificationSante
from .sante.s2_provisionnement.agent import AgentS2ProvissionnementSante
from .services.sp_ratio import (
    LR_CIBLE_MAX, LR_PLANCHER_VRAISEMBLABLE, charge_sinistres, loss_ratio,
    statut_loss_ratio,
)


def _p1(**kw):
    base = dict(success=True, primes_acquises=340_830.0, nb_assures=500,
                salaire_brut=45_000.0, taux_cotisation_pct=1.51,
                taux_rente_ipp=0.60)
    base.update(kw)
    return base


def _p2(pa=340_830.0, nb=500):
    return {"success": True, "sorties_p3": {
        "age": 40.0, "taux_ip": 0.00336, "taux_itt": 0.042,
        "prob_maintien_6m": 0.578, "prob_maintien_12m": 0.345,
        "prob_maintien_24m": 0.145, "esperance_duree_ip": 24.8,
        "salaire_brut": 45_000.0, "taux_rente_ipp": 0.60,
        "primes_acquises": pa, "nb_assures": nb, "franchise_jours": 90}}


def _p3_run(**kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return AgentP3ProvissionnementPrevoyance(verbose=False).run(
            generer_graphiques=False, **kw)


class TestLeSpNeDependPasDuTauxDeCotisation(unittest.TestCase):
    """D07 — l'invariant le plus simple, et le plus révélateur."""

    def test_faire_varier_le_taux_de_cotisation_ne_change_pas_le_sp(self):
        ratios = {}
        for taux in (0.5, 1.51, 5.0, 50.0, 200.0):
            resultat = _p3_run(result_p1=_p1(taux_cotisation_pct=taux),
                               result_p2=_p2())
            ratios[taux] = round(float(resultat["loss_ratio"]), 6)
        distincts = set(ratios.values())
        self.assertEqual(
            1, len(distincts),
            "Le S/P suit le taux de cotisation : %s. Avant correction, "
            "lr = taux_cotisation / 100 x 0,80 — un pourcentage de SALAIRE "
            "pris pour un rapport de sinistres a primes." % ratios)

    def test_le_sp_publie_est_vraisemblable(self):
        resultat = _p3_run(result_p1=_p1(), result_p2=_p2())
        lr = float(resultat["loss_ratio"])
        self.assertGreaterEqual(
            lr, LR_PLANCHER_VRAISEMBLABLE,
            "S/P publie = %.4f. Au taux nominal de 1,51 %%, l'agent publiait "
            "1,21 %% avant correction." % lr)

    def test_la_provenance_du_sp_est_publiee(self):
        resultat = _p3_run(result_p1=_p1(), result_p2=_p2())
        source = resultat.get("sorties_p4", {}).get("source_lr") or \
            resultat.get("source_lr")
        self.assertTrue(
            source, "Le S/P doit publier sa provenance : un lecteur doit "
                    "savoir s'il vient de sinistres observes ou d'une "
                    "reference de marche.")


class TestLeSpEstBorneDesDeuxCotes(unittest.TestCase):
    """D06 — un S/P trop bas signale une erreur d'assiette."""

    def test_un_sp_invraisemblablement_bas_est_rejete(self):
        statut, motif = statut_loss_ratio(0.0121)
        self.assertEqual(
            "NON VALIDÉE", statut,
            "Un S/P de 1,21 %% doit etre rejete ; obtenu %r (%s)"
            % (statut, motif))
        self.assertIn("assiette", motif.lower())

    def test_un_sp_normal_reste_valide(self):
        statut, _ = statut_loss_ratio(0.68)
        self.assertEqual("VALIDÉE", statut)

    def test_un_sp_deficitaire_est_rejete(self):
        statut, _ = statut_loss_ratio(1.35)
        self.assertEqual("NON VALIDÉE", statut)

    def test_les_bornes_sont_declarees_et_ordonnees(self):
        self.assertLess(LR_PLANCHER_VRAISEMBLABLE, LR_CIBLE_MAX)


class TestLaChargeDeSinistresIncluLesProvisions(unittest.TestCase):
    """La définition de place : prestations versées + provisions constituées."""

    def test_la_charge_additionne_prestations_et_provisions(self):
        self.assertAlmostEqual(150.0, charge_sinistres(100.0, 50.0))

    def test_omettre_les_provisions_sous_estime_le_sp(self):
        avec, _ = loss_ratio(100.0, 200.0, provisions_constituees=60.0)
        sans, _ = loss_ratio(100.0, 200.0, provisions_constituees=0.0)
        self.assertGreater(
            avec, sans,
            "Inclure les provisions doit AUGMENTER le S/P : c'est la part "
            "provisionnee de la sinistralite de l'exercice.")

    def test_s2_publie_les_deux_grandeurs_cote_a_cote(self):
        with contextlib.redirect_stdout(io.StringIO()):
            s1 = AgentS1TarificationSante(verbose=False).run(
                nb_assures=5000, age_moyen=38, contrat="collectif",
                garantie_niveau="confort", chargement_pct=0.18,
                generer_graphiques=False)
            s2 = AgentS2ProvissionnementSante(verbose=False).run(
                result_s1=s1, generer_graphiques=False)
        self.assertIn("loss_ratio_prestations_seules", s2)
        self.assertGreater(
            s2["loss_ratio"], s2["loss_ratio_prestations_seules"],
            "Le S/P avec provisions doit depasser celui des seules "
            "prestations reglees.")


class TestLaPrimeIpEstAnnuelleCommeLaPrimeItt(unittest.TestCase):
    """D02 — deux primes sur la même base ne se divisent pas différemment."""

    def _primes(self, duree):
        with contextlib.redirect_stdout(io.StringIO()):
            resultat = AgentP1TarificationPrevoyance(verbose=False).run(
                age=40, salaire_brut=45_000, categorie="employe",
                duree_contrat=duree, generer_graphiques=False)
        return resultat["primes_pures"]

    def test_la_prime_ip_ne_depend_pas_de_la_duree_du_contrat(self):
        valeurs = {d: round(self._primes(d)["ip"], 4) for d in (1, 5, 10, 20)}
        self.assertEqual(
            1, len(set(valeurs.values())),
            "La prime IP suit la duree du contrat : %s. Avant correction, "
            "1 937,60 EUR a 1 an contre 96,88 EUR a 20 ans." % valeurs)

    def test_la_prime_itt_est_invariante_elle_aussi(self):
        """La propriété de référence : c'est l'asymétrie qui révélait le défaut."""
        valeurs = {d: round(self._primes(d)["itt"], 4) for d in (1, 20)}
        self.assertEqual(1, len(set(valeurs.values())))


if __name__ == "__main__":
    unittest.main()
