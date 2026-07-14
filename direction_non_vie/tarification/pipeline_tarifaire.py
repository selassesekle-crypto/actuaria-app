"""
direction_non_vie/tarification/pipeline_tarifaire.py — LE PRODUIT VENDABLE.

Assemble, à partir d'un PlanTarifaire SIGNÉ et d'un portefeuille, le tarif
complet — sans connaître la moindre LoB. C'est ce qui répond à « tarifez-moi ce
contrat » (étape 5) et ce qui tarife la décennale par YAML seul (étape 7).

Chaîne :
    A2.fit(df, plan).transform(df)                 → contrat A2→A3 (INV-1)
    construire_matrice_x(..., plan=plan, df, cible) → conformité déclarative (INV-2/3/4)
    GLM fréquence (Poisson, offset log-exposition)
    GLM coût moyen  — FAMILLE DÉCLARÉE DANS LE PLAN (plan.famille_severite)
    écrêtement des graves + coefficient d'équilibre (étape 6, INV-8)
    → TarifNonVie.tarifer(contrat)                 → reproduit le portefeuille (INV-7)

Rien ici ne « sait » ce qu'est une voiture ou un chantier : tout vient du plan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.genmod import families as _families

from core.plan_tarifaire import PlanTarifaire
from core.conformite_reglementaire import construire_matrice_x
from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing

# Chargements par défaut (auto). Déclarables dans le plan (étape 6) ; ici en
# repli neutre pour la fréquence/coût. Taxes : auto 33 %, MRH 30 %, RC 9 %.
CHARGEMENTS_DEFAUT = {
    "frais": 0.15, "commission": 0.10, "marge": 0.03, "taxes": 0.33,
}


# ══════════════════════════════════════════════════════════════════════════════
#  GLM de COÛT MOYEN — la famille est DÉCLARÉE, plus codée en dur (schéma étendu)
# ══════════════════════════════════════════════════════════════════════════════
def _famille_cout_statsmodels(famille_severite: str):
    """Traduit plan.famille_severite en famille statsmodels. 'lognormal' est
    traité à part (régression gaussienne sur log(coût) + correction de Duan) :
    statsmodels n'a pas de famille log-normale native, et c'est la façon
    actuarielle standard de l'ajuster."""
    if famille_severite == "gamma":
        return _families.Gamma(link=_families.links.Log())
    if famille_severite == "inverse_gaussienne":
        return _families.InverseGaussian(link=_families.links.Log())
    if famille_severite == "lognormal":
        return "lognormal"
    raise ValueError(f"famille_severite inconnue : '{famille_severite}'.")


class ModeleCout:
    """GLM de coût moyen ajusté selon la famille DÉCLARÉE dans le plan. Interface
    predict() uniforme (retour sur l'échelle du coût, quelle que soit la famille)."""

    def __init__(self, famille_severite: str, resultat, duan: float = 1.0):
        self.famille_severite = famille_severite
        self._res = resultat
        self._duan = duan   # smearing de Duan (lognormal uniquement)

    def predict(self, Xc) -> np.ndarray:
        mu = np.asarray(self._res.predict(Xc), dtype=float)
        if self.famille_severite == "lognormal":
            # OLS sur log(coût) → retour à l'échelle coût avec correction de Duan
            return np.exp(mu) * self._duan
        return mu   # gamma / inverse-gaussienne : lien log → déjà en euros


def ajuster_glm_cout(Xc: pd.DataFrame, y_cout: pd.Series,
                     famille_severite: str = "gamma") -> ModeleCout:
    """Ajuste le GLM de COÛT MOYEN sur les sinistres (>0), selon la famille
    déclarée. Xc : matrice de conception AVEC constante ; y_cout : coût moyen
    par sinistre (>0)."""
    fam = _famille_cout_statsmodels(famille_severite)
    y = np.asarray(y_cout, dtype=float)
    if fam == "lognormal":
        ylog = np.log(np.clip(y, 1e-9, None))
        res = sm.OLS(ylog, Xc).fit()
        resid = ylog - np.asarray(res.predict(Xc), dtype=float)
        duan = float(np.mean(np.exp(resid)))   # smearing estimator (Duan, 1983)
        return ModeleCout("lognormal", res, duan)
    res = sm.GLM(y, Xc, family=fam).fit(maxiter=200, disp=False)
    return ModeleCout(famille_severite, res)


# ══════════════════════════════════════════════════════════════════════════════
#  TarifNonVie — le livrable commercial (étape 5)
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class TarifNonVie:
    plan: PlanTarifaire
    a2: AgentA2Preprocessing          # fitté sur le portefeuille
    glm_frequence: Any                # GLMResults (Poisson, offset log-expo)
    glm_cout: ModeleCout              # famille déclarée dans le plan
    features: List[str]               # colonnes conformes réellement ajustées
    ecretement: float = 0.0           # prime de graves unitaire (étape 6)
    coefficient_equilibre: float = 1.0  # k (INV-8)
    chargements: Dict[str, float] = field(default_factory=lambda: dict(CHARGEMENTS_DEFAUT))

    # ── Prédiction interne, partagée par tarifer() et le portefeuille (INV-7) ──
    def _design(self, df: pd.DataFrame) -> pd.DataFrame:
        X = self.a2.transform(df)
        return sm.add_constant(X[self.features], has_constant="add")

    def _taux_frequence(self, Xc) -> np.ndarray:
        # offset=0 → taux annuel PAR UNITÉ d'exposition (la prime le remultiplie).
        return np.asarray(
            self.glm_frequence.predict(Xc, offset=np.zeros(len(Xc))), dtype=float)

    def predire_portefeuille(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prédictions vectorisées sur un portefeuille — MÊME chemin que
        tarifer(), pour que l'un reproduise l'autre à 1e-6 (INV-7)."""
        Xc = self._design(df)
        expo = pd.to_numeric(df[self.plan.exposition], errors="coerce").to_numpy(dtype=float)
        freq = self._taux_frequence(Xc)
        cout = self.glm_cout.predict(Xc)
        prime_pure = self.coefficient_equilibre * (freq * cout + self.ecretement) * expo
        return pd.DataFrame({
            "frequence_annuelle": freq, "cout_moyen": cout,
            "prime_pure": prime_pure, "exposition": expo,
        }, index=df.index)

    def tarifer(self, contrat: dict, exposition: float = 1.0) -> dict:
        """« Tarifez-moi ce contrat. » Le livrable qui vend (étape 5)."""
        df = pd.DataFrame([{**contrat, self.plan.exposition: exposition}])
        Xc = self._design(df)
        freq = float(self._taux_frequence(Xc)[0])
        cout = float(self.glm_cout.predict(Xc)[0])
        prime_pure = self.coefficient_equilibre * (freq * cout + self.ecretement) * exposition
        ch = self.chargements
        pc = (prime_pure * (1 + ch["frais"]) * (1 + ch["marge"])
              / (1 - ch["commission"]))
        return {
            "frequence_annuelle": round(freq, 5),
            "cout_moyen": round(cout, 2),
            "prime_pure": round(prime_pure, 2),
            "prime_commerciale_ht": round(pc, 2),
            "prime_ttc": round(pc * (1 + ch["taxes"]), 2),
            "plan": self.plan.empreinte(),   # traçabilité ACPR
        }

    def grille(self, variable: str) -> pd.DataFrame:
        """Relativités exportables (ce que l'assureur met dans son SI)."""
        rel = {}
        for f in self.plan.facteurs:
            if f.nom != variable:
                continue
            for col in f.colonnes_produites():
                if col in self.features:
                    coef = float(getattr(self.glm_frequence, "params", {}).get(col, 0.0))
                    rel[col] = round(float(np.exp(coef)), 4)
        return pd.DataFrame({"colonne": list(rel), "relativite_frequence": list(rel.values())})


# ══════════════════════════════════════════════════════════════════════════════
#  Stabilité temporelle — UNE SEULE fonction Gini pour le test ET le walk-forward
# ══════════════════════════════════════════════════════════════════════════════
def gini_lorenz(y_true, y_pred) -> float:
    """Gini de concentration (2·aire de Lorenz − 1), en triant les contrats par
    la PRÉDICTION. UNE SEULE définition, utilisée à l'identique pour le Gini de
    test ET le Gini walk-forward — c'est ce qui rend impossible la « métrique
    divergente » de B9 (INV-6)."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if len(y_true) == 0:
        return 0.0
    ordre = np.argsort(-y_pred, kind="mergesort")
    y = y_true[ordre]
    total = float(y.sum())
    if total <= 0:
        return 0.0
    cum_y = np.cumsum(y) / total
    cum_pop = np.arange(1, len(y) + 1) / len(y)
    _trap = getattr(np, "trapezoid", None) or np.trapz
    return float(2.0 * _trap(cum_y, cum_pop) - 1.0)


def evaluer_stabilite_temporelle(portefeuille: pd.DataFrame, plan: PlanTarifaire,
                                 col_temps: Optional[str] = None,
                                 n_fenetres: int = 4,
                                 models_path: str = "/tmp/actuaria",
                                 audit_path: str = "/tmp/actuaria") -> Dict[str, Any]:
    """Compare le Gini de TEST (une coupe train/test) au Gini WALK-FORWARD
    (fenêtres glissantes), avec la MÊME fonction gini_lorenz et la MÊME
    spécification (le pipeline plan) des deux côtés. INV-6 : l'écart relatif doit
    rester < 0,40 — sinon la métrique ou la spécification diverge (B9)."""
    df = portefeuille.copy().reset_index(drop=True)
    if col_temps and col_temps in df.columns:
        df = df.sort_values(col_temps, kind="mergesort").reset_index(drop=True)
    n = len(df)
    col_freq, col_expo = plan.cible_frequence, plan.exposition

    def _gini_sur(tarif, sous_df):
        pred = tarif.predire_portefeuille(sous_df)
        attendu = pred["frequence_annuelle"].to_numpy() * pred["exposition"].to_numpy()
        return gini_lorenz(sous_df[col_freq].to_numpy(), attendu)

    def _fit(sous_df):
        return pipeline_complet(sous_df, plan, equilibrer=False,
                                models_path=models_path, audit_path=audit_path)

    # ── Gini de TEST : derniers 20 % en test, le reste en apprentissage ──────
    cut = int(n * 0.8)
    tarif_tt = _fit(df.iloc[:cut])
    gini_test = _gini_sur(tarif_tt, df.iloc[cut:])

    # ── Gini WALK-FORWARD : fenêtres glissantes (fenêtre étendue) ────────────
    bornes = np.linspace(int(n * 0.4), n, n_fenetres + 1).astype(int)
    ginis = []
    for i in range(n_fenetres):
        tr_end, te_end = int(bornes[i]), int(bornes[i + 1])
        if te_end <= tr_end:
            continue
        tarif_i = _fit(df.iloc[:tr_end])
        ginis.append(_gini_sur(tarif_i, df.iloc[tr_end:te_end]))
    gini_wf = float(np.mean(ginis)) if ginis else 0.0

    ecart = (abs(gini_wf - gini_test) / abs(gini_test)
             if gini_test else float("inf"))
    return {"gini_test": gini_test, "gini_wf": gini_wf,
            "ginis_fenetres": ginis, "ecart_relatif": ecart}


# ══════════════════════════════════════════════════════════════════════════════
#  pipeline_complet — de A1 au tarif, piloté PAR LE PLAN (étapes 2→6)
# ══════════════════════════════════════════════════════════════════════════════
def pipeline_complet(portefeuille: pd.DataFrame, plan: PlanTarifaire,
                     chargements: Optional[dict] = None,
                     quantile_ecretement: float = 0.995,
                     equilibrer: bool = True,
                     models_path: str = "/tmp/actuaria",
                     audit_path: str = "/tmp/actuaria") -> TarifNonVie:
    """Ajuste le tarif complet à partir du seul plan signé. Aucune connaissance
    métier codée : A2 (fit/transform), conformité déclarative, GLM fréquence,
    GLM coût (famille du plan), écrêtement + équilibre (étape 6)."""
    df = portefeuille.copy()
    col_freq, col_cout, col_expo = (plan.cible_frequence, plan.cible_cout,
                                    plan.exposition)

    # ── A2 : fit / transform (le contrat A2→A3, INV-1) ──────────────────────
    a2 = AgentA2Preprocessing(models_path=models_path, audit_path=audit_path,
                              verbose=False).fit(df, plan)
    X = a2.transform(df)

    # ── Conformité DÉCLARATIVE (liste blanche = plan, INV-2/3/4) ────────────
    mx = construire_matrice_x(
        list(plan.colonnes_produites()), plan=plan, df=X,
        col_cible=[col_freq, col_cout],
        contexte=f"pipeline_complet — {plan.lob}")
    features = list(mx)

    Xc = sm.add_constant(X[features], has_constant="add")
    expo = pd.to_numeric(X[col_expo], errors="coerce").clip(lower=1e-9)
    y_freq = pd.to_numeric(X[col_freq], errors="coerce").astype(float)

    # ── GLM FRÉQUENCE (Poisson, offset log-exposition) ──────────────────────
    glm_freq = sm.GLM(y_freq, Xc,
                      family=_families.Poisson(link=_families.links.Log()),
                      offset=np.log(expo)).fit(maxiter=200, disp=False)

    # ── Écrêtement des graves (étape 6) : la charge grave est réintégrée en
    #    charge MOYENNE sur tout le portefeuille, pas au contrat ──────────────
    cout_total = pd.to_numeric(X[col_cout], errors="coerce").astype(float).fillna(0.0)
    seuil = float(cout_total[cout_total > 0].quantile(quantile_ecretement)) \
        if (cout_total > 0).any() else 0.0
    cout_ecrete = cout_total.clip(upper=seuil) if seuil > 0 else cout_total
    charge_grave = float((cout_total - cout_ecrete).sum())
    prime_grave_unitaire = charge_grave / float(expo.sum()) if float(expo.sum()) > 0 else 0.0

    # ── GLM COÛT MOYEN — FAMILLE DÉCLARÉE DANS LE PLAN ──────────────────────
    # On ajuste la sévérité là où un COÛT est OBSERVÉ (cout_ecrete > 0), pas
    # seulement là où un sinistre est COMPTÉ (count > 0). Sur données réelles
    # (freMTPL2) ~9 100 contrats ont ClaimNb > 0 SANS montant enregistré : leur
    # sévérité vaudrait 0 et casserait le GLM Gamma. La FRÉQUENCE, elle, garde
    # tous les contrats (le comptage est observé). Sur données synthétiques où
    # cout > 0 ⇔ count > 0, ce masque est STRICTEMENT identique à l'ancien —
    # INV-7 et INV-8 restent donc inchangés.
    mask = ((cout_ecrete > 0) & (y_freq > 0)).to_numpy()
    if mask.any():
        sev = (cout_ecrete.to_numpy()[mask] / y_freq.to_numpy()[mask]).astype(float)
        glm_cout = ajuster_glm_cout(Xc[mask], sev, plan.famille_severite)
    else:   # aucun coût observé : coût moyen constant (dégénéré mais défini)
        glm_cout = ajuster_glm_cout(Xc.iloc[:1], pd.Series([1.0]),
                                    plan.famille_severite)

    tarif = TarifNonVie(
        plan=plan, a2=a2, glm_frequence=glm_freq, glm_cout=glm_cout,
        features=features, ecretement=prime_grave_unitaire,
        coefficient_equilibre=1.0,
        chargements=dict(chargements or CHARGEMENTS_DEFAUT))

    # ── Coefficient d'ÉQUILIBRE technique k (INV-8) ─────────────────────────
    # k = Σ charge observée / Σ (prime_pure prédite). Après ce calage, la prime
    # pure totale reproduit la charge totale à ±1 %.
    if equilibrer:
        pred = tarif.predire_portefeuille(df)
        somme_predite = float(pred["prime_pure"].sum())
        somme_observee = float(cout_total.sum())
        if somme_predite > 0 and somme_observee > 0:
            tarif.coefficient_equilibre = somme_observee / somme_predite
    return tarif
