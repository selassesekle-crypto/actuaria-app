"""
Tests unitaires — Agent S1 Léonie : Tarification Frais de Santé
Direction Santé-Prévoyance · Équipe Santé
Sources : DREES 2023, ANI 2013, Art. L911-7 CSS
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from direction_sante_prevoyance.sante.s1_tarification.agent import AgentS1TarificationSante


@pytest.fixture(scope="module")
def s1():
    return AgentS1TarificationSante(verbose=False)


@pytest.fixture(scope="module")
def r_confort(s1):
    return s1.run(nb_assures=1000, age_moyen=40, contrat="collectif",
                  garantie_niveau="confort", chargement_pct=0.18,
                  generer_graphiques=False)


# ── T1 : Succès et structure du retour ────────────────────────────────────────
def test_s1_success_et_structure(r_confort):
    """Le retour doit contenir toutes les clés standard ActuarIA."""
    assert r_confort["success"] is True
    assert r_confort["statut_rag"] in ("VERT", "AMBRE", "ROUGE")
    assert r_confort["erreur"] is None
    assert "commentaire" in r_confort
    assert "graphiques" in r_confort
    assert "hypotheses" in r_confort


# ── T2 : Prime pure > 0 et < seuil raisonnable ────────────────────────────────
def test_s1_prime_pure_positive(r_confort):
    """Prime pure unitaire doit être positive et cohérente avec le marché.
    Référence : marché mutuelles individuelles France (FNMF 2023) = 500-1500€/an.
    """
    pp = r_confort["prime_pure"]
    assert pp > 0, f"Prime pure doit être positive, obtenu : {pp}"
    assert pp < 3000, f"Prime pure hors plage marché : {pp:.0f}€ (attendu < 3000€)"


# ── T3 : Hiérarchie des niveaux de garantie ───────────────────────────────────
def test_s1_hierarchie_garanties(s1):
    """eco < confort < premium — fact_garantie appliqué correctement sur la charge."""
    r_eco     = s1.run(nb_assures=1000, age_moyen=40, contrat="collectif",
                       garantie_niveau="eco",     generer_graphiques=False)
    r_confort = s1.run(nb_assures=1000, age_moyen=40, contrat="collectif",
                       garantie_niveau="confort", generer_graphiques=False)
    r_premium = s1.run(nb_assures=1000, age_moyen=40, contrat="collectif",
                       garantie_niveau="premium", generer_graphiques=False)
    assert r_eco["prime_pure"] < r_confort["prime_pure"] < r_premium["prime_pure"], (
        f"Hiérarchie incorrecte : eco={r_eco['prime_pure']:.0f} "
        f"confort={r_confort['prime_pure']:.0f} premium={r_premium['prime_pure']:.0f}"
    )
    ratio = r_premium["prime_pure"] / r_confort["prime_pure"]
    assert abs(ratio - 1.40) < 0.05, (
        f"Ratio premium/confort = {ratio:.3f}, attendu 1.40 "
        f"(fact_garantie eco=0.60, confort=1.00, premium=1.40)"
    )


# ── T4 : ANI individuel vs collectif ──────────────────────────────────────────
def test_s1_ani_individuel_conforme(s1):
    """ANI 2013 ne s'applique qu'aux collectifs (Art. L911-7 CSS).
    Un contrat individuel doit toujours retourner ani_conforme=True.
    """
    r = s1.run(nb_assures=100, age_moyen=35, contrat="individuel",
               garantie_niveau="eco", generer_graphiques=False)
    assert r["ani_conforme"] is True, (
        "Contrat individuel doit être conforme ANI automatiquement "
        "(Art. L911-7 CSS — ANI applicable uniquement au collectif)"
    )
    notes = [v.get("note","") for v in r["ani_detail"]["detail"].values()]
    assert any("N/A" in n for n in notes), (
        "Notes ANI pour contrat individuel doivent contenir N/A"
    )


# ── T5 : Loss Ratio = 1/(1+chargement) ────────────────────────────────────────
def test_s1_lr_tarification(s1):
    """LR de tarification = prime_pure / prime_comm = 1/(1+chargement).
    C'est le LR que la tarification vise, pas un LR observé.
    """
    for chargement in [0.15, 0.18, 0.20, 0.25]:
        r = s1.run(nb_assures=1000, age_moyen=40, contrat="collectif",
                   garantie_niveau="confort", chargement_pct=chargement,
                   generer_graphiques=False)
        lr = r["ratio_sp_attendu"]
        lr_attendu = 1 / (1 + chargement)
        assert abs(lr - lr_attendu) < 0.001, (
            f"LR avec chargement={chargement:.0%} : "
            f"obtenu={lr:.4f}, attendu={lr_attendu:.4f}"
        )


# ── T6 : Sorties vers S2 complètes ────────────────────────────────────────────
def test_s1_sorties_s2(r_confort):
    """sorties_s2 doit contenir toutes les clés attendues par S2."""
    s2 = r_confort.get("sorties_s2", {})
    for cle in ["primes_acquises", "sinistres_attendus", "loss_ratio_attendu",
                "sinistralite_par_poste", "nb_assures", "prime_pure_unitaire"]:
        assert cle in s2, f"Clé manquante dans sorties_s2 : '{cle}'"
    assert s2["primes_acquises"] > 0
    assert s2["sinistres_attendus"] > 0
    assert 0 < s2["loss_ratio_attendu"] < 1


# ── T7 : Données réelles depuis builder ───────────────────────────────────────
def test_s1_donnees_reelles(s1):
    """S1 doit utiliser les données réelles du builder quand result_a2 est fourni."""
    import numpy as np
    import pandas as pd
    from direction_sante_prevoyance.services.sp_data_builder import SPDataBuilder

    np.random.seed(42)
    n = 500
    df = pd.DataFrame({
        "age":      np.random.randint(25, 60, n),
        "sexe":     np.random.choice(["M","F"], n),
        "garanties":np.random.choice(["confort","premium"], n),
        "sinistres_medecine": np.random.exponential(200, n),
    })
    r_build = SPDataBuilder(verbose=False).construire(df)
    r = s1.run(result_a2=r_build, nb_assures=500, age_moyen=40,
               contrat="collectif", generer_graphiques=False)
    assert r["success"] is True
    assert r.get("source_donnees") == "donnees_reelles_a2", (
        f"Source attendue 'donnees_reelles_a2', obtenu : {r.get('source_donnees')}"
    )
    assert r["nb_assures"] == n
