"""
demos/pipeline_3lob_a1_a6_demo.py — NON-RÉGRESSION MULTI-LoB, CHAÎNE A1→A6.

Rejoue la chaîne complète A1 (ingestion) → A2 (preprocessing) → A3 (GLM) →
A4 (ML) → A6 (comparaison/gate RAG) sur TROIS branches Non-Vie à la fois —
auto, mrh, rcpro — à partir de portefeuilles synthétiques déterministes.

Pourquoi ce script existe (à REJOUER après tout changement touchant plusieurs
LoB) : plusieurs correctifs de modélisation transverses ont été faits (encodage
csp auto & secteur_activite rcpro label→one_hot, bug calendrier age_logement
mrh). Un correctif « à un endroit » peut casser une autre LoB silencieusement.
Ce script confirme, pour chaque LoB, que :
  · la chaîne A1→A6 s'enchaîne SANS exception ;
  · A1/A2 détectent la bonne sous-branche ;
  · A2/A3/A4 renvoient success=True et A6 produit un statut RAG ;
  · les colonnes CORRIGÉES sortent bien d'A2 au bon encodage (csp_*, one-hot ;
    secteur_activite_*, one-hot ; zone_geographique_enc pour le calendrier mrh).

Ce qu'il ne teste PAS (volontairement) : la COULEUR du statut RAG. Sur données
synthétiques le walk-forward est bruité — une fenêtre rouge suffit à passer en
AMBRE, et c'est le comportement CORRECT du gate. On vérifie que la chaîne tourne
et reste cohérente, pas qu'elle certifie VERT.

Dépendances : cœur seul (sklearn/statsmodels/numpy/pandas). Les modèles ML
boostés (xgboost/lightgbm/catboost) et le DL (torch) sont optionnels — A4 les
saute proprement s'ils sont absents (cf. requirements-optional.txt). Le script
n'installe rien et n'écrit que dans un dossier temporaire.

Sortie : un tableau récapitulatif par LoB. Code de sortie 1 si une LoB n'a pas
traversé la chaîne (utilisable en garde de non-régression).
"""
import logging
import os
import sys
import tempfile
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
# Silence le bavardage INFO des agents — on affiche l'essentiel nous-mêmes.
logging.getLogger("actuaria").setLevel(logging.ERROR)
# Le générateur de rapport logue en ERROR l'absence de python-docx (optionnel) :
# bruit attendu et sans effet ici, on le passe sous silence pour la lisibilité.
logging.getLogger("actuaria.tarif.rapport").setLevel(logging.CRITICAL)

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)

from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
from core.plan_tarifaire import PlanTarifaire  # Phase 1 : A3 reçoit le plan signé

TMP = os.path.join(tempfile.gettempdir(), "actuaria_demo_3lob")
ANNEES = [2019, 2020, 2021, 2022, 2023]


# ── Portefeuilles synthétiques déterministes (structure causale connue) ───────
def portefeuille_auto(n, rng):
    age = rng.integers(18, 85, n).astype(float)
    bm = np.clip(rng.normal(0.9, 0.2, n), 0.5, 3.5)
    expo = np.clip(rng.beta(5, 1, n), 0.2, 1.0)
    nb = rng.poisson(0.25 * np.exp(0.9 * np.log(bm) + 0.7 * (age < 25)) * expo)
    return pd.DataFrame({
        "id_contrat": range(n), "annee_souscription": rng.choice(ANNEES, n),
        "exposition": expo, "age": age, "bonus_malus": bm,
        "anciennete_permis": np.clip(age - 18, 0, None).astype(float),
        "puissance_fiscale": rng.integers(4, 15, n).astype(float),
        "age_vehicule": rng.integers(0, 20, n).astype(float),
        "valeur_venale": np.clip(rng.normal(15000, 6000, n), 1000, None),
        "garantie": rng.choice(["Tiers", "TousRisques"], n),
        "carburant": rng.choice(["Essence", "Diesel", "Electrique"], n, p=[.5, .4, .1]),
        "csp": rng.choice(["Cadre", "Employe", "Retraite"], n, p=[.35, .45, .20]),
        "usage": rng.choice(["Prive", "Pro"], n, p=[.8, .2]),
        "antecedents_sinistres_n1": rng.poisson(0.15, n).astype(float),
        "kilometrage_annuel": np.clip(rng.normal(12000, 4000, n), 1000, None),
        "milieu_geographique": rng.choice(["Urbain", "Periurbain", "Rural"], n),
        "nb_sinistres": nb.astype(float),
        "cout_total_sinistres": np.where(nb > 0, rng.gamma(2, 1200, n), 0.0),
    })


def portefeuille_mrh(n, rng):
    surface = np.clip(rng.normal(80, 30, n), 15, None)
    annee_c = rng.integers(1950, 2020, n)
    alarme = rng.integers(0, 2, n).astype(float)
    dv = rng.integers(0, 2, n).astype(float)
    zone = rng.choice(["Urbaine", "Periurbaine", "Rurale"], n, p=[.4, .35, .25])
    zr = np.select([zone == "Urbaine", zone == "Periurbaine", zone == "Rurale"],
                   [.35, 0., -.35])
    expo = np.clip(rng.beta(5, 1, n), 0.1, 1.0)
    age_log = 2026 - annee_c
    nb = rng.poisson(np.exp(-2.2 - .35 * alarme - .25 * dv + .015 * age_log + zr) * expo)
    return pd.DataFrame({
        "id_contrat": range(n), "annee_souscription": rng.choice(ANNEES, n),
        "exposition": expo, "surface_m2": surface,
        "etage": rng.integers(0, 10, n).astype(float),
        "alarme": alarme, "double_vitrage": dv,
        "garantie_vol": rng.integers(0, 2, n).astype(float),
        "zone_geographique": zone,
        "statut_occupation": rng.choice(["Proprietaire", "Locataire"], n, p=[.6, .4]),
        "type_logement": rng.choice(["Maison", "Appartement"], n, p=[.5, .5]),
        "valeur_mobilier": np.clip(rng.normal(25000, 10000, n), 2000, None),
        "annee_construction": annee_c,
        "nb_sinistres": nb.astype(float),
        "cout_total_sinistres": np.where(nb > 0, rng.gamma(2, 1500, n), 0.0),
    })


def portefeuille_rcpro(n, rng):
    nb_sal = rng.integers(1, 200, n).astype(float)
    antec = rng.poisson(0.4, n).astype(float)
    secteur = rng.choice(["BTP", "Conseil", "Commerce", "Industrie"], n, p=[.3, .3, .2, .2])
    sr = np.select([secteur == "BTP", secteur == "Conseil", secteur == "Commerce",
                    secteur == "Industrie"], [.50, -.40, -.10, .40])
    forme = rng.choice(["SARL", "SAS", "SA", "EI"], n, p=[.4, .3, .1, .2])
    fr = np.select([forme == "SARL", forme == "SAS", forme == "SA", forme == "EI"],
                   [0., 0., -.15, .20])
    tg = rng.choice(["Base", "Etendue"], n, p=[.6, .4])
    expo = np.clip(rng.beta(5, 1, n), 0.1, 1.0)
    nb = rng.poisson(np.exp(-1.9 + .004 * nb_sal + .35 * antec + sr + fr
                           + .15 * (tg == "Etendue")) * expo)
    return pd.DataFrame({
        "id_contrat": range(n), "annee_souscription": rng.choice(ANNEES, n),
        "exposition": expo, "nb_salaries": nb_sal,
        "anciennete_entreprise_ans": rng.integers(0, 30, n).astype(float),
        "antecedents_sinistres_3ans": antec,
        "ca_annuel_eur": np.clip(rng.lognormal(13, 1, n), 50_000, None),
        "secteur_activite": secteur, "type_garantie": tg, "forme_juridique": forme,
        "nb_sinistres": nb.astype(float),
        "cout_total_sinistres": np.where(nb > 0, rng.gamma(2, 4000, n), 0.0),
    })


# ── Un passage A1→A6, avec vérifications de cohérence ─────────────────────────
def run_lob(nom, df, marqueurs_attendus):
    """Retourne (ok: bool, ligne_resume: dict). ok=False si crash ou incohérence."""
    print(f"\n{'=' * 72}\n  LoB = {nom.upper()}  ({len(df):,} contrats, "
          f"{int(df['nb_sinistres'].sum()):,} sinistres)\n{'=' * 72}")
    try:
        r1 = AgentA1Ingestion(audit_path=TMP, verbose=False).run(
            branche="non_vie", sous_branche=nom, dataframe=df)
        r2 = AgentA2Preprocessing(audit_path=TMP, verbose=False).run(result_a1=r1)
        plan = PlanTarifaire.depuis_yaml(os.path.join(RACINE, "plans", f"{nom}.yaml"))
        r3 = AgentA3GLM(models_path=TMP, audit_path=TMP, verbose=False).run(
            result_a2=r2, plan=plan, generer_graphiques=False)
        r4 = AgentA4ML(models_path=TMP, audit_path=TMP, verbose=False).run(
            result_a2=r2, result_a3=r3, plan=plan, calcul_shap=False,
            generer_graphiques=False)
        r6 = AgentA6Comparaison(models_path=TMP, audit_path=TMP, verbose=False).run(
            result_a2=r2, result_a3=r3, result_a4=r4, result_a5=None,
            col_cible="nb_sinistres", generer_graphiques=False,
            generer_rapport_equipe=False, environnement="production",
            profil_valide_par="Actuaire")
    except Exception as e:
        import traceback
        print(f"  !!! CRASH : {type(e).__name__}: {e}")
        traceback.print_exc()
        return False, {"lob": nom, "verdict": "CRASH"}

    detected = r2.get("branche", "?")
    succes = (bool(r2.get("success")) and bool(r3.get("success"))
              and bool(r4.get("success")) and "statut_rag" in r6)
    met = (r3.get("metriques") or {}).get("poisson", {})
    rap4 = r4.get("rapport", {})
    bt = r6.get("backtest", {})
    cols = list(r2["dataframe"].columns)

    # Phase 1 : plus de DÉTECTION (A1 reçoit sous_branche). Ce contrôle vérifie
    # désormais la PROPAGATION : la LoB déclarée à A1 doit ressortir intacte d'A2
    # (c'est result_a2['branche'] que lisent A3/A4/A5).
    print(f"  sous-branche déclarée → A2  : {detected} "
          f"{'✓' if detected == nom else '✗ (attendu ' + nom + ')'}")
    print(f"  success A2/A3/A4 + A6 statut : {succes}")
    print(f"  A3 GLM Poisson              : Gini={met.get('gini', float('nan')):.4f}")
    print(f"  A4 modèles entraînés        : {rap4.get('modeles_testes')}")
    print(f"     sautés (libs absentes)   : "
          f"{[a.split(' :')[0] for a in rap4.get('alertes', [])]}")
    print(f"  A6 statut RAG               : {r6.get('statut_rag')} | "
          f"modèle={r6.get('modele_production', {}).get('modele')} | "
          f"A/E={bt.get('ae_ratio')} | fenêtres_rouge={bt.get('n_fenetres_rouge')}")

    # Correctifs transverses : les colonnes attendues sortent-elles d'A2 ?
    marqueurs_ok = True
    for m in marqueurs_attendus:
        present = [c for c in cols if c.startswith(m)]
        etat = "✓" if present else "✗ ABSENT"
        if not present:
            marqueurs_ok = False
        print(f"  correctif '{m}*' en sortie A2 : {present} {etat}")

    ok = succes and (detected == nom) and marqueurs_ok
    return ok, {
        "lob": nom, "detection": detected, "gini": met.get("gini"),
        "statut": r6.get("statut_rag"), "verdict": "OK" if ok else "INCOHÉRENT",
    }


def main():
    os.makedirs(TMP, exist_ok=True)
    rng = np.random.default_rng(2026)
    plan = [
        ("auto", portefeuille_auto(12000, rng), ["csp_"]),
        ("mrh", portefeuille_mrh(12000, rng), ["zone_geographique_enc"]),
        ("rcpro", portefeuille_rcpro(12000, rng), ["secteur_activite_"]),
    ]
    resume = []
    for nom, df, marqueurs in plan:
        _, ligne = run_lob(nom, df, marqueurs)
        resume.append(ligne)

    print(f"\n{'=' * 72}\n  RÉCAPITULATIF\n{'=' * 72}")
    print(f"  {'LoB':6s} {'détection':10s} {'Gini':>7s} {'statut':>7s}  verdict")
    for r in resume:
        g = f"{r['gini']:.4f}" if r.get("gini") is not None else "   -  "
        print(f"  {r['lob']:6s} {r.get('detection', '-'):10s} {g:>7s} "
              f"{str(r.get('statut', '-')):>7s}  {r['verdict']}")

    echecs = [r["lob"] for r in resume if r["verdict"] != "OK"]
    if echecs:
        print(f"\n  ✗ NON-RÉGRESSION ÉCHOUÉE — LoB en défaut : {echecs}")
        sys.exit(1)
    print("\n  ✓ Les 3 LoB traversent A1→A6 sans accroc, correctifs en place.")


if __name__ == "__main__":
    main()
