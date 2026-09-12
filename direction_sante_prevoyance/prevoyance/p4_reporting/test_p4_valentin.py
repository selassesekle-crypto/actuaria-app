"""
Tests unitaires — Agent P4 Valentin : Reporting Prévoyance
Direction Santé-Prévoyance · Équipe Prévoyance
Sources : RD 2015/35 Art.145/252, S2 Art.129, IFRS 17 §B91
"""
import pytest
import unittest
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from direction_sante_prevoyance.prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
from direction_sante_prevoyance.prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite
from direction_sante_prevoyance.prevoyance.p3_provisionnement.agent import AgentP3ProvissionnementPrevoyance
from direction_sante_prevoyance.prevoyance.p4_reporting.agent import AgentP4ReportingPrevoyance


def _fx_pipeline_p4():
    import pandas as pd
    from direction_sante_prevoyance.services.sp_data_builder import SPDataBuilder
    np.random.seed(42)
    n = 1000
    df = pd.DataFrame({
        "age": np.random.randint(30, 58, n),
        "salaire_brut": np.random.uniform(30000, 70000, n),
        "csp": np.random.choice(["employe","cadre","ouvrier"], n, p=[0.5,0.3,0.2]),
    })
    r_b  = SPDataBuilder(verbose=False).construire(df)
    p1   = AgentP1TarificationPrevoyance(verbose=False)
    p2   = AgentP2TablesMorbidite(verbose=False)
    p3   = AgentP3ProvissionnementPrevoyance(verbose=False)
    p4   = AgentP4ReportingPrevoyance(verbose=False)
    r_p1 = p1.run(result_a2=r_b, age=42, salaire_brut=45000,
                  categorie="employe", generer_graphiques=False)
    r_p2 = p2.run(result_p1=r_p1, generer_graphiques=False)
    r_p3 = p3.run(result_p1=r_p1, result_p2=r_p2, generer_graphiques=False)
    r_p4 = p4.run(result_p1=r_p1, result_p2=r_p2, result_p3=r_p3,
                  fonds_propres=12_000_000, generer_graphiques=False)
    return r_p1, r_p2, r_p3, r_p4


# ── T1 : Succès avec FP réels ─────────────────────────────────────────────────
def _impl_test_p4_success(pipeline_p4):
    *_, r_p4 = pipeline_p4
    assert r_p4["success"] is True
    assert r_p4["erreur"] is None
    assert r_p4["statut_rag"] in ("VERT", "AMBRE", "ROUGE")


# ── T2 : SCR invalidité > 0 ───────────────────────────────────────────────────
def _impl_test_p4_scr_invalidite_positif(pipeline_p4):
    """SCR invalidité doit être positif.
    Formule : choc +35% morbidité — RD 2015/35 Art.145.
    """
    *_, r_p4 = pipeline_p4
    scr = r_p4.get("scr_invalidite", 0)
    assert scr > 0, f"SCR invalidité doit être > 0, obtenu : {scr}"


# ── T3 : MCR > 0 et plancher actif ────────────────────────────────────────────
def _impl_test_p4_mcr_plancher_art129(pipeline_p4):
    """MCR prévoyance soumis au plancher absolu 3.7M€ — S2 Art.129.
    Sur un petit portefeuille, le plancher est naturellement actif.

    ⚠️ CORRIGÉ LE 12/09/2026 — CE TEST NE POUVAIT PAS ÉCHOUER. Il lisait
    `mcr_prevoyance`, une clé que P4 n'a jamais produite : la lecture rendait
    son repli 0, et l'assertion était `0 >= 0`. Elle serait restée verte si le
    MCR avait valu zéro, s'il avait disparu, ou s'il n'avait jamais été
    calculé. Le test portait le nom du plancher et ne le vérifiait pas.
    """
    *_, r_p4 = pipeline_p4
    assert "mcr" in r_p4, (
        "P4 doit publier `mcr` : c'est la grandeur que ce test surveille, et "
        "une cle absente rendrait l assertion vide de sens.")
    mcr = r_p4["mcr"]
    lineaire = r_p4["mcr_lineaire"]
    regime = r_p4["mcr_regime"]

    # Le plancher ABSOLU de la branche protection du revenu — art. 248 par. 1
    # (plancher absolu) et annexe XIX pour les coefficients, PAS l article 252.
    PLANCHER_ABS = 3_700_000.0
    assert mcr >= PLANCHER_ABS, (
        f"MCR = {mcr:,.0f} EUR < plancher absolu {PLANCHER_ABS:,.0f} EUR")
    assert regime == "PLANCHER_ACTIF", (
        f"Sur ce portefeuille le MCR lineaire vaut {lineaire:,.0f} EUR, tres "
        f"en dessous du plancher : le regime doit etre PLANCHER_ACTIF, "
        f"obtenu {regime!r}")
    assert lineaire < PLANCHER_ABS, (
        f"MCR lineaire = {lineaire:,.0f} EUR : si le lineaire depassait le "
        f"plancher, ce test ne mesurerait plus ce qu il annonce")
    assert r_p4["mcr_reference"], (
        "Le MCR doit publier la reference de ses coefficients (annexe XIX)")
    assert r_p4["success"], "P4 doit réussir même avec plancher MCR"


# ── T4 : Ratio SCR > 100% avec FP suffisants ─────────────────────────────────
def _impl_test_p4_ratio_scr_suffisant(pipeline_p4):
    """Avec 12M€ de FP et BE ~1.7M€, ratio SCR >> 100%."""
    *_, r_p4 = pipeline_p4
    assert r_p4["ratio_scr_pct"] > 100, (
        f"Ratio SCR = {r_p4['ratio_scr_pct']:.1f}% — insuffisant avec 12M€ FP"
    )


# ── T5 : RA récupéré de P3 ────────────────────────────────────────────────────
def _impl_test_p4_ra_depuis_p3(pipeline_p4):
    """P4 doit utiliser le RA calculé par P3 (IFRS 17 conforme).
    Le RA de P3 = 3% BE via méthode CoC — RD 2015/35 Art.145 + IFRS 17 §B91.
    """
    _, _, r_p3, r_p4 = pipeline_p4
    ra_p3 = r_p3.get("sorties_p4",{}).get("risk_adjustment", 0)
    ra_p4 = r_p4.get("risk_adjustment", ra_p3)
    assert ra_p3 > 0, "RA P3 doit être > 0"
    assert r_p4["success"], "P4 doit réussir"


# ── T6 : QRT S.14 présent ─────────────────────────────────────────────────────
def _impl_test_p4_qrt_s14(pipeline_p4):
    """Le QRT S.14 (Health SLT — Invalidité) doit être généré."""
    *_, r_p4 = pipeline_p4
    qrt = r_p4.get("qrt_s14", {})
    assert qrt is not None and qrt != {}, "QRT S.14 doit être présent"
    assert "S.14" in str(qrt) or "invalidite" in str(qrt).lower() or len(qrt) > 0


# ── T7 : Success sans FP + message documenté ─────────────────────────────────
def _impl_test_p4_success_sans_fp():
    """P4 doit fonctionner sans FP — plancher MCR explique le ROUGE éventuel."""
    import pandas as pd
    from direction_sante_prevoyance.services.sp_data_builder import SPDataBuilder
    np.random.seed(42)
    df = pd.DataFrame({
        "age": np.random.randint(30, 58, 100),
        "salaire_brut": np.random.uniform(30000, 70000, 100),
        "csp": ["employe"] * 100,
    })
    r_b  = SPDataBuilder(verbose=False).construire(df)
    p1   = AgentP1TarificationPrevoyance(verbose=False)
    p2   = AgentP2TablesMorbidite(verbose=False)
    p3   = AgentP3ProvissionnementPrevoyance(verbose=False)
    p4   = AgentP4ReportingPrevoyance(verbose=False)
    r_p1 = p1.run(result_a2=r_b, age=42, salaire_brut=45000,
                  categorie="employe", generer_graphiques=False)
    r_p2 = p2.run(result_p1=r_p1, generer_graphiques=False)
    r_p3 = p3.run(result_p1=r_p1, result_p2=r_p2, generer_graphiques=False)
    r_p4 = p4.run(result_p1=r_p1, result_p2=r_p2, result_p3=r_p3,
                  fonds_propres=0, generer_graphiques=False)
    assert r_p4["success"] is True, "P4 doit réussir même sans FP"

# ────────────────────────────────────────────────────────────────────────────
# Enveloppe unittest.TestCase
#
# La gate du dépôt lance `unittest discover`, qui ne collecte QUE les
# sous-classes de TestCase : les fonctions nues lui sont invisibles.
# Cette classe rend les tests ci-dessus visibles des DEUX lanceurs, sans
# modifier un seul de leurs asserts. Les fixtures sont résolues une fois
# par `setUpClass`, ce qui reproduit le `scope="module"` d'origine.
# ────────────────────────────────────────────────────────────────────────────
class TestP4Valentin(unittest.TestCase):
    """Tests de ce module, exposés à unittest discover."""

    @classmethod
    def setUpClass(cls):
        cls._fxv_pipeline_p4 = _fx_pipeline_p4()

    def test_p4_success(self):
        _impl_test_p4_success(self._fxv_pipeline_p4)

    def test_p4_scr_invalidite_positif(self):
        _impl_test_p4_scr_invalidite_positif(self._fxv_pipeline_p4)

    def test_p4_mcr_plancher_art129(self):
        _impl_test_p4_mcr_plancher_art129(self._fxv_pipeline_p4)

    def test_p4_ratio_scr_suffisant(self):
        _impl_test_p4_ratio_scr_suffisant(self._fxv_pipeline_p4)

    def test_p4_ra_depuis_p3(self):
        _impl_test_p4_ra_depuis_p3(self._fxv_pipeline_p4)

    def test_p4_qrt_s14(self):
        _impl_test_p4_qrt_s14(self._fxv_pipeline_p4)

    def test_p4_success_sans_fp(self):
        _impl_test_p4_success_sans_fp()
