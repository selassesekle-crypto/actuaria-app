"""
Tests unitaires — Agent P2 Rayan : Tables de Morbidité
Direction Santé-Prévoyance · Équipe Prévoyance
Sources : BCAC 2019 (matrice Markov), TD 88-90
"""
import pytest
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from direction_sante_prevoyance.prevoyance.p1_tarification.agent import AgentP1TarificationPrevoyance
from direction_sante_prevoyance.prevoyance.p2_tables_morbidite.agent import AgentP2TablesMorbidite


@pytest.fixture(scope="module")
def r_p1():
    return AgentP1TarificationPrevoyance(verbose=False).run(
        age=42, salaire_brut=45000, categorie="employe",
        franchise_jours=90, generer_graphiques=False)


@pytest.fixture(scope="module")
def r_p2(r_p1):
    return AgentP2TablesMorbidite(verbose=False).run(
        result_p1=r_p1, generer_graphiques=False)


# ── T1 : Succès et structure ───────────────────────────────────────────────────
def test_p2_success(r_p2):
    assert r_p2["success"] is True
    assert r_p2["statut_rag"] in ("VERT", "AMBRE", "ROUGE")
    assert r_p2["erreur"] is None


# ── T2 : Matrice Markov 4×4 stochastique ──────────────────────────────────────
def test_p2_markov_stochastique(r_p2):
    """La matrice de transition doit être stochastique : chaque ligne somme à 1.
    États : Actif, ITT, IP, Décès — Source BCAC 2019.
    """
    mat = r_p2.get("matrice_P", [])
    assert len(mat) == 4, f"Matrice doit être 4×4, obtenu {len(mat)}×?"
    for i, row in enumerate(mat):
        assert len(row) == 4, f"Ligne {i} : {len(row)} états au lieu de 4"
        s = sum(row)
        assert abs(s - 1.0) < 1e-6, (
            f"Ligne {i} non stochastique : Σ={s:.8f} (attendu 1.000000)"
        )


# ── T3 : Probabilités de transition cohérentes ────────────────────────────────
def test_p2_transitions_coherentes(r_p2):
    """Toutes les probabilités de transition doivent être dans [0, 1]."""
    mat = r_p2.get("matrice_P", [])
    for i, row in enumerate(mat):
        for j, prob in enumerate(row):
            assert 0 <= prob <= 1.0 + 1e-9, (
                f"Probabilité P[{i},{j}]={prob:.6f} hors [0,1]"
            )


# ── T4 : Probabilité de maintien décroissante ─────────────────────────────────
def test_p2_maintien_decroissant(r_p2):
    """La probabilité de rester en ITT doit décroître avec le temps.
    Référence : courbe de maintien BCAC 2019.
    """
    pm = r_p2.get("prob_maintien", {})
    pm6  = pm.get("mois_6",  0)
    pm12 = pm.get("mois_12", 0)
    pm24 = pm.get("mois_24", 0)
    assert 0 < pm6 < 1,  f"P(maintien 6m) = {pm6:.3f} hors ]0,1["
    assert 0 < pm12 < 1, f"P(maintien 12m) = {pm12:.3f} hors ]0,1["
    assert pm6 > pm12 > pm24 > 0, (
        f"Maintien non décroissant : 6m={pm6:.3f} 12m={pm12:.3f} 24m={pm24:.3f}"
    )


# ── T5 : Probabilité maintien 6m ∈ plage BCAC ────────────────────────────────
def test_p2_maintien_6m_bcac(r_p2):
    """P(maintien 6m) doit être dans [20%, 80%] — référence BCAC 2019."""
    pm6 = r_p2.get("prob_maintien", {}).get("mois_6", 0)
    assert 0.20 < pm6 < 0.80, (
        f"P(maintien 6m) = {pm6:.3f} hors plage BCAC [0.20, 0.80]"
    )


# ── T6 : Sorties vers P3 complètes ────────────────────────────────────────────
def test_p2_sorties_p3(r_p2):
    """sorties_p3 doit contenir les clés attendues par P3."""
    s3 = r_p2.get("sorties_p3", {})
    for cle in ["age", "categorie", "taux_ip", "taux_itt"]:
        assert cle in s3, f"Clé manquante dans sorties_p3 : '{cle}'"
    assert s3["taux_ip"] >= 0
    assert s3["taux_itt"] >= 0


# ── T7 : Croissance morbidité avec l'âge ─────────────────────────────────────
def test_p2_morbidite_croissante_age():
    """Le taux d'invalidité doit augmenter avec l'âge — TD 88-90."""
    p1 = AgentP1TarificationPrevoyance(verbose=False)
    p2 = AgentP2TablesMorbidite(verbose=False)
    r_35 = p2.run(result_p1=p1.run(age=35, salaire_brut=40000, categorie="employe",
                                     generer_graphiques=False), generer_graphiques=False)
    r_55 = p2.run(result_p1=p1.run(age=55, salaire_brut=40000, categorie="employe",
                                     generer_graphiques=False), generer_graphiques=False)
    ip_35 = r_35.get("sorties_p3",{}).get("taux_ip", 0)
    ip_55 = r_55.get("sorties_p3",{}).get("taux_ip", 0)
    assert ip_55 > ip_35, (
        f"Taux IP à 55 ans ({ip_55:.4f}) doit être > 35 ans ({ip_35:.4f}) — TD 88-90"
    )
