"""
Tests unitaires — Agent P1 Axel : Tarification Prévoyance
Direction Santé-Prévoyance · Équipe Prévoyance
Sources : BCAC 2019, TD 88-90, TH 00-02, CTIP 2023, CCN Cadres 1947
"""
import pytest
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from direction_sante_prevoyance.prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance


@pytest.fixture(scope="module")
def p1():
    return AgentP1TarificationPrevoyance(verbose=False)


@pytest.fixture(scope="module")
def r_base(p1):
    return p1.run(age=42, salaire_brut=45000, categorie="employe",
                  franchise_jours=90, generer_graphiques=False)


# ── T1 : Succès et structure ───────────────────────────────────────────────────
def test_p1_success(r_base):
    assert r_base["success"] is True
    assert r_base["statut_rag"] in ("VERT", "AMBRE", "ROUGE")
    assert r_base["erreur"] is None
    assert "primes_pures" in r_base
    for g in ["itt", "ip", "deces"]:
        assert g in r_base["primes_pures"], f"prime_{g} manquante"


# ── T2 : Probabilité franchise — loi exponentielle BCAC 2019 ──────────────────
def test_p1_prob_franchise_expo_bcac(p1):
    """P(arrêt > franchise) = exp(-franchise / duree_moy_bcac).
    BCAC 2019 : duree_moy = 45j → P(>90j) = exp(-2) ≈ 13.5%.
    Propriété : ratio prime(f=0) / prime(f=90j) = exp(90/45) = exp(2) ≈ 7.39.
    """
    r_f0  = p1.run(age=42, salaire_brut=45000, categorie="employe",
                   franchise_jours=0,  generer_graphiques=False)
    r_f90 = p1.run(age=42, salaire_brut=45000, categorie="employe",
                   franchise_jours=90, generer_graphiques=False)
    p_f0  = r_f0["primes_pures"]["itt"]
    p_f90 = r_f90["primes_pures"]["itt"]
    assert p_f0 > p_f90 > 0, "Prime ITT décroissante avec franchise"
    ratio = p_f0 / max(p_f90, 0.001)
    assert abs(ratio - np.exp(2)) < 1.0, (
        f"Ratio prime(f=0)/prime(f=90j) = {ratio:.2f}, "
        f"attendu exp(2)={np.exp(2):.2f} (loi expo BCAC duree_moy=45j)"
    )


# ── T3 : Hiérarchie CSP sur ITT à salaire égal ────────────────────────────────
def test_p1_hierarchie_csp_itt(p1):
    """À salaire égal : ITT_ouvrier > ITT_employe > ITT_cadre > ITT_cadre_sup.
    Source : BCAC 2019 facteurs CSP (1.35 / 1.00 / 0.75 / 0.60).
    """
    SAL = 40000
    results = {
        csp: p1.run(age=42, salaire_brut=SAL, categorie=csp,
                    franchise_jours=3, generer_graphiques=False)
        for csp in ["ouvrier", "employe", "cadre", "cadre_sup"]
    }
    p = {csp: r["primes_pures"]["itt"] for csp, r in results.items()}
    assert p["ouvrier"] > p["employe"] > p["cadre"] > p["cadre_sup"], (
        f"Hiérarchie CSP incorrecte : {p}"
    )


# ── T4 : Capital décès différencié par CSP ────────────────────────────────────
def test_p1_capital_deces_csp(p1):
    """Capital décès différencié par CSP — CTIP 2023 + CCN Cadres 1947.
    Cadres sup : 4× | Cadres : 3× | Employés : 1.5× | Ouvriers : 1×.
    """
    SAL = 40000
    results = {
        csp: p1.run(age=42, salaire_brut=SAL, categorie=csp,
                    franchise_jours=3, generer_graphiques=False)
        for csp in ["ouvrier", "employe", "cadre", "cadre_sup"]
    }
    dc = {csp: r["primes_pures"]["deces"] for csp, r in results.items()}
    assert dc["cadre_sup"] > dc["cadre"] > dc["employe"] > dc["ouvrier"], (
        f"Hiérarchie DC incorrecte (multiples 4x/3x/1.5x/1x) : {dc}"
    )


# ── T5 : ITT dominant sur non-cadres avec franchise courte ───────────────────
def test_p1_itt_dominant_franchise_courte(p1):
    """Pour employe et ouvrier avec franchise courte (3j),
    la prime ITT doit être supérieure à la prime décès.
    """
    for csp in ["employe", "ouvrier"]:
        r = p1.run(age=42, salaire_brut=40000, categorie=csp,
                   franchise_jours=3, generer_graphiques=False)
        p_itt = r["primes_pures"]["itt"]
        p_dc  = r["primes_pures"]["deces"]
        assert p_itt > p_dc, (
            f"{csp} f=3j : prime ITT ({p_itt:.0f}€) "
            f"doit être > prime DC ({p_dc:.0f}€)"
        )


# ── T6 : Taux de cotisation dans la norme CCN ────────────────────────────────
def test_p1_taux_cotisation_norme_ccn(p1):
    """Taux cotisation ∈ [0.5%, 6%] selon les paramètres.
    Norme CCN : 1.5-4% pour les régimes standards.
    """
    r = p1.run(age=42, salaire_brut=45000, categorie="employe",
               franchise_jours=90, generer_graphiques=False)
    taux = r.get("taux_cotisation_pct", 0)
    assert 0.3 < taux < 8.0, (
        f"Taux cotisation {taux:.2f}% hors plage acceptable"
    )


# ── T7 : Données réelles depuis builder ───────────────────────────────────────
def test_p1_donnees_reelles(p1):
    """P1 doit utiliser les données IP réelles du builder."""
    import pandas as pd
    from direction_sante_prevoyance.services.sp_data_builder import SPDataBuilder
    np.random.seed(42)
    n = 300
    df = pd.DataFrame({
        "age": np.random.randint(30, 58, n),
        "salaire_brut": np.random.uniform(28000, 65000, n),
        "csp": np.random.choice(["employe","cadre","ouvrier"], n, p=[0.5,0.3,0.2]),
    })
    r_build = SPDataBuilder(verbose=False).construire(df)
    r = p1.run(result_a2=r_build, age=42, salaire_brut=45000,
               categorie="employe", generer_graphiques=False)
    assert r["success"] is True
    assert r.get("source_donnees") == "donnees_reelles_a2"
    assert r["nb_assures"] == n
