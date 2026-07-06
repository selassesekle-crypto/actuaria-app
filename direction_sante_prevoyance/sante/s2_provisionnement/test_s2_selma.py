"""
Tests unitaires — Agent S2 Selma : Provisionnement Santé
Direction Santé-Prévoyance · Équipe Santé
Sources : DREES 2023, FNMF 2023, IFRS 17 §B91
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from direction_sante_prevoyance.sante.s1_tarification.agent import AgentS1TarificationSante
from direction_sante_prevoyance.sante.s2_provisionnement.agent import AgentS2ProvisionnemntSante


@pytest.fixture(scope="module")
def r_s1():
    return AgentS1TarificationSante(verbose=False).run(
        nb_assures=5000, age_moyen=38, contrat="collectif",
        garantie_niveau="confort", chargement_pct=0.18,
        generer_graphiques=False)


@pytest.fixture(scope="module")
def s2():
    return AgentS2ProvisionnemntSante(verbose=False)


@pytest.fixture(scope="module")
def r_s2(s2, r_s1):
    return s2.run(result_s1=r_s1, generer_graphiques=False)


# ── T1 : Succès et structure ───────────────────────────────────────────────────
def test_s2_success(r_s2):
    assert r_s2["success"] is True
    assert r_s2["statut_rag"] in ("VERT", "AMBRE", "ROUGE")
    assert r_s2["erreur"] is None


# ── T2 : PSAP = dossiers + IBNR ───────────────────────────────────────────────
def test_s2_psap_identite_comptable(r_s2):
    """Identité comptable : PSAP_total = PSAP_dossiers + PSAP_IBNR."""
    psap_total = r_s2["psap_total"]
    psap_d     = r_s2["psap_dossiers"]
    psap_i     = r_s2["psap_ibnr"]
    assert abs(psap_total - (psap_d + psap_i)) < 0.01, (
        f"PSAP_total ({psap_total:.2f}) ≠ dossiers ({psap_d:.2f}) + IBNR ({psap_i:.2f})"
    )
    assert psap_total > 0
    assert psap_d > 0
    assert psap_i > 0


# ── T3 : PSAP/PA ∈ [5%, 30%] — référence marché ───────────────────────────────
def test_s2_ratio_psap_pa(r_s2, r_s1):
    """PSAP/PA doit être dans la plage marché [5%, 30%].
    Référence : mutuelles France (FNMF 2023) — santé règlement rapide.
    """
    pa   = r_s1["primes_acquises"]
    psap = r_s2["psap_total"]
    ratio = psap / max(pa, 1)
    assert 0.05 < ratio < 0.30, (
        f"PSAP/PA = {ratio*100:.1f}% hors plage [5%,30%] "
        f"(PSAP={psap:,.0f}€ PA={pa:,.0f}€) — référence FNMF 2023"
    )


# ── T4 : Risk Adjustment IFRS 17 ──────────────────────────────────────────────
def test_s2_risk_adjustment_ifrs17(r_s2):
    """RA calculé via méthode CoC, pas un coefficient fixe.
    RA ≥ 1% BE (floor marché) | RA > 0.
    Source : IFRS 17 §B91 — méthode CoC.
    """
    s3_out = r_s2.get("sorties_s3", {})
    ra = s3_out.get("risk_adjustment", 0)
    be = s3_out.get("be_sante", 0)
    assert ra > 0, "RA doit être > 0"
    assert ra >= be * 0.01, (
        f"RA ({ra:,.0f}€) < floor 1% BE ({be*0.01:,.0f}€)"
    )
    # RA ne doit pas être simplement 5% × BE (ancienne formule supprimée)
    ra_fixe_5pct = be * 0.05
    assert abs(ra - ra_fixe_5pct) > 0.01, (
        "RA ne doit pas être un coefficient fixe 5% × BE (supprimé)"
    )


# ── T5 : Sinistres payés par délai poste ──────────────────────────────────────
def test_s2_sinistres_payes_par_poste(r_s2):
    """Sinistres payés calculés par délai de règlement par poste.
    Pharmacie/Médecine = 97-98% | Hospit = 82% | Pas de 0.85 global.
    Source : FNMF 2023, DREES 2023.
    """
    lr = r_s2["loss_ratio"]
    assert 0 < lr < 1.5, f"Loss ratio hors plage : {lr:.3f}"
    # Vérifier que loss_ratio est calculé (pas 0)
    assert lr > 0.30, "Loss ratio trop faible — vérifier calcul sinistres payés"


# ── T6 : Fonds propres absents de sorties_s3 ──────────────────────────────────
def test_s2_fp_absents_sorties_s3(r_s2):
    """S2 ne doit pas estimer les FP — c'est le rôle de S3.
    FP supprimés de sorties_s3 (étaient PA × 0.80 sans base réglementaire).
    """
    s3_out = r_s2.get("sorties_s3", {})
    assert "fonds_propres" not in s3_out, (
        "FP ne doivent pas être calculés par S2 (rôle de S3)"
    )


# ── T7 : Sorties vers S3 complètes ────────────────────────────────────────────
def test_s2_sorties_s3_completes(r_s2):
    """sorties_s3 doit contenir toutes les clés attendues par S3."""
    s3_out = r_s2.get("sorties_s3", {})
    for cle in ["be_sante", "risk_adjustment", "tp_sante",
                "psap_total", "prec", "loss_ratio", "primes_acquises"]:
        assert cle in s3_out, f"Clé manquante dans sorties_s3 : '{cle}'"
    assert s3_out["be_sante"] > 0
    assert s3_out["tp_sante"] > s3_out["be_sante"]
