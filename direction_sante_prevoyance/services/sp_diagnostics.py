"""
sp_diagnostics.py — Contrôles qualité données Santé-Prévoyance

Équivalent de nv_triangle_diagnostics.py pour la Direction SP.
Contrôles spécifiques aux données mutuelle (Format M),
institution de prévoyance (Format IP) et assureur mixte (Format MX).

Utilisé par SPDataBuilder et les agents S1/P1 pour valider
la cohérence des données avant tarification/provisionnement.
"""

from typing import Dict, List, Tuple
import logging

logger = logging.getLogger("actuaria.sp.diagnostics")

# ── Constantes de référence marché ────────────────────────────────────────────
# Source : DREES 2023, FNMF 2023, BCAC 2019, CTIP 2023

# Plages LR acceptables par type de portefeuille
LR_PLAGES = {
    "mutuelle":       (0.55, 0.85),   # FNMF 2023 : LR mutuelles individuelles
    "ip_collective":  (0.60, 0.90),   # CTIP 2023 : LR IP collectives
    "assureur_mixte": (0.58, 0.88),   # Combiné
}

# Plages taux d'arrêt ITT acceptables
TAUX_ARRET_PLAGES = {
    "ouvrier":   (0.05, 0.20),   # BCAC 2019 — forte sinistralité
    "employe":   (0.03, 0.12),
    "cadre":     (0.02, 0.08),
    "cadre_sup": (0.01, 0.05),
}

# Coûts moyens sinistres santé par poste — DREES 2023
COUTS_REF_SANTE = {
    "medecine":        (50,   500),    # €/assuré/an
    "pharmacie":       (80,   600),
    "hospitalisation": (200, 5000),
    "dentaire":        (50,  1500),
    "optique":         (50,  1000),
}

# ── Diagnostics Format M (Mutuelle santé) ─────────────────────────────────────

def diagnostiquer_format_m(df, rapport: Dict) -> Tuple[int, List[str]]:
    """
    Contrôles qualité spécifiques Format M (mutuelle santé individuelle/collective).

    Contrôles :
    D1 — LR observé dans la plage marché mutuelles (FNMF 2023)
    D2 — Coûts moyens sinistres par poste cohérents (DREES 2023)
    D3 — Distribution d'âges cohérente (18-85 ans, pic 40-60)
    D4 — Cohérence niveaux de garantie (eco < confort < premium)

    Returns
    -------
    (score_bonus, alertes) — score de 0 à 20 (bonus sur score SPDataBuilder)
    """
    import pandas as pd
    alertes = []
    score   = 0

    # D1 — LR observé
    if "cotisation" in df.columns and "sinistres_sante" in df.columns:
        lr = df["sinistres_sante"].sum() / max(df["cotisation"].sum(), 1)
        lo, hi = LR_PLAGES["mutuelle"]
        if lo <= lr <= hi:
            score += 8
        elif lr < lo:
            alertes.append(f"⚠️ LR={lr:.1%} < {lo:.0%} — sinistres faibles vs cotisations")
        else:
            alertes.append(f"⚠️ LR={lr:.1%} > {hi:.0%} — ratio élevé à contrôler")
    else:
        score += 4  # demi-point si données incomplètes
        alertes.append("ℹ️ LR non calculable — colonnes cotisation/sinistres_sante absentes")

    # D2 — Coûts moyens par poste
    postes_present = 0
    for poste, (lo, hi) in COUTS_REF_SANTE.items():
        col = f"sinistres_{poste}" if f"sinistres_{poste}" in df.columns else None
        if col:
            cout_moy = df[col].mean()
            if lo <= cout_moy <= hi:
                postes_present += 1
            else:
                alertes.append(
                    f"⚠️ Coût moyen {poste}={cout_moy:.0f}€ hors plage [{lo},{hi}]€ (DREES 2023)"
                )
    if postes_present > 0:
        score += min(6, postes_present * 2)

    # D3 — Distribution d'âges
    if "age" in df.columns:
        ages = df["age"].dropna()
        pct_hors_plage = ((ages < 18) | (ages > 85)).mean()
        if pct_hors_plage < 0.01:
            score += 4
        else:
            alertes.append(f"⚠️ {pct_hors_plage:.1%} des âges hors [18,85]")

    # D4 — Cohérence garanties si multi-niveaux
    if "garanties" in df.columns and "cotisation" in df.columns:
        cots = df.groupby("garanties")["cotisation"].mean()
        if "eco" in cots and "confort" in cots and cots["eco"] < cots["confort"]:
            score += 2
        elif "eco" in cots and "confort" in cots:
            alertes.append("⚠️ Cotisation eco ≥ confort — incohérence tarifaire")

    return min(score, 20), alertes


def diagnostiquer_format_ip(df, rapport: Dict) -> Tuple[int, List[str]]:
    """
    Contrôles qualité spécifiques Format IP (institution de prévoyance).

    Contrôles :
    D1 — Taux d'arrêt ITT par CSP dans les plages BCAC 2019
    D2 — Salaires cohérents avec les CSP déclarées (INSEE 2023)
    D3 — Distribution d'âges salariés (22-65 ans)
    D4 — Taux d'invalidité cohérent avec TD 88-90

    Returns
    -------
    (score_bonus, alertes)
    """
    import pandas as pd
    alertes = []
    score   = 0

    # D1 — Taux d'arrêt ITT par CSP
    if "arrets_itt" in df.columns and "categorie" in df.columns:
        for csp, (lo, hi) in TAUX_ARRET_PLAGES.items():
            mask = df["categorie"] == csp
            if mask.sum() < 10:
                continue
            taux = (df.loc[mask, "arrets_itt"] > 0).mean()
            if lo <= taux <= hi:
                score += 4
            else:
                alertes.append(
                    f"⚠️ Taux arrêt {csp}={taux:.1%} hors plage BCAC [{lo:.0%},{hi:.0%}]"
                )
    else:
        alertes.append("ℹ️ Taux arrêt non vérifiable — colonnes arrets_itt/categorie absentes")
        score += 2

    # D2 — Salaires par CSP (références INSEE DADS 2023)
    SALAIRES_REF = {
        "ouvrier":   (18000, 40000),
        "employe":   (20000, 55000),
        "cadre":     (40000, 100000),
        "cadre_sup": (70000, 250000),
    }
    if "salaire_brut" in df.columns and "categorie" in df.columns:
        for csp, (lo, hi) in SALAIRES_REF.items():
            mask = df["categorie"] == csp
            if mask.sum() < 5:
                continue
            sal_moy = df.loc[mask, "salaire_brut"].mean()
            if lo <= sal_moy <= hi:
                score += 3
            else:
                alertes.append(
                    f"⚠️ Salaire moy {csp}={sal_moy:,.0f}€ hors plage INSEE [{lo:,},{hi:,}]€"
                )
    else:
        score += 2

    # D3 — Âges salariés
    if "age" in df.columns:
        ages = df["age"].dropna()
        pct_hors = ((ages < 22) | (ages > 65)).mean()
        if pct_hors < 0.02:
            score += 4
        else:
            alertes.append(f"⚠️ {pct_hors:.1%} des âges hors [22,65] — vérifier données")

    # D4 — Taux invalidité
    if "invalidites_ip" in df.columns:
        taux_ip = (df["invalidites_ip"] > 0).mean()
        if 0.001 <= taux_ip <= 0.05:
            score += 5
        elif taux_ip == 0:
            alertes.append("ℹ️ Taux IP = 0% — normal si portefeuille jeune/court terme")
            score += 2
        else:
            alertes.append(f"⚠️ Taux IP={taux_ip:.2%} inhabituel (TD 88-90 : 0.1%-5%)")
    else:
        score += 2

    return min(score, 20), alertes


def diagnostiquer_format_mx(df, rapport: Dict) -> Tuple[int, List[str]]:
    """
    Contrôles qualité spécifiques Format MX (assureur mixte S+P).

    Contrôles :
    D1 — Poly-sinistralité dans une plage acceptable
    D2 — Cohérence entre sinistres santé et arrêts ITT (corrélation attendue)
    D3 — Taille minimale pour analyses MX fiables (≥ 200 assurés)

    Returns
    -------
    (score_bonus, alertes)
    """
    import pandas as pd
    alertes = []
    score   = 0

    # D1 — Poly-sinistralité
    if "sinistres_sante" in df.columns and "arrets_itt" in df.columns:
        sin_s = (df["sinistres_sante"] > 0)
        arr_p = (df["arrets_itt"] > 0)
        poly  = (sin_s & arr_p).mean() * 100
        if poly <= 15:
            score += 8
        elif poly <= 25:
            alertes.append(f"⚠️ Poly-sinistralité {poly:.1f}% élevée — risque accumulation S+P")
            score += 4
        else:
            alertes.append(f"❌ Poly-sinistralité {poly:.1f}% > 25% — anomalie à investiguer")
    else:
        alertes.append("ℹ️ Poly-sinistralité non calculable — données S ou P manquantes")
        score += 3

    # D2 — Corrélation santé / arrêts (doit être positive mais modérée)
    if "sinistres_sante" in df.columns and "arrets_itt" in df.columns:
        try:
            corr = df[["sinistres_sante", "arrets_itt"]].corr().iloc[0, 1]
            if 0.05 <= corr <= 0.60:
                score += 7
                alertes.append(
                    f"ℹ️ Corrélation santé/arrêts = {corr:.2f} (cohérente — ρ EIOPA=0.25)"
                )
            elif corr < 0.05:
                score += 4
                alertes.append(f"ℹ️ Corrélation faible ({corr:.2f}) — S et P peu liés")
            else:
                alertes.append(f"⚠️ Corrélation élevée ({corr:.2f}) — risque sous-estimation diversification")
                score += 3
        except Exception:
            score += 3

    # D3 — Taille minimale
    n = len(df)
    if n >= 500:
        score += 5
    elif n >= 200:
        score += 3
        alertes.append(f"ℹ️ {n} assurés — analyses MX plus fiables à partir de 500")
    else:
        alertes.append(f"⚠️ {n} assurés — taille insuffisante pour analyses MX robustes (min 200)")

    return min(score, 20), alertes


def diagnostiquer(df, format_detecte: str, rapport: Dict) -> Dict:
    """
    Point d'entrée unique — sélectionne le diagnostic selon le format.

    Parameters
    ----------
    df : pd.DataFrame — données normalisées
    format_detecte : str — "M", "IP", "MX", "A"
    rapport : dict — rapport de qualité SPDataBuilder (modifié en place)

    Returns
    -------
    dict — {score_bonus, alertes, format, nb_assures}
    """
    score_bonus = 0
    alertes     = []

    if format_detecte == "M":
        score_bonus, alertes = diagnostiquer_format_m(df, rapport)
    elif format_detecte == "IP":
        score_bonus, alertes = diagnostiquer_format_ip(df, rapport)
    elif format_detecte == "MX":
        score_bonus, alertes = diagnostiquer_format_mx(df, rapport)
    elif format_detecte == "A":
        # Format agrégé triangulaire — diagnostics minimaux
        score_bonus = 10
        alertes.append("ℹ️ Format A (agrégé) — diagnostics individuels non applicables")

    # Ajouter les alertes au rapport
    for a in alertes:
        if a.startswith("❌"):
            rapport["erreurs"].append(a) if "erreurs" in rapport else rapport["alertes"].append(a)
        elif a.startswith("⚠️"):
            rapport["alertes"].append(a)
        else:
            rapport["infos"].append(a)

    if alertes:
        logger.info(
            f"sp_diagnostics [{format_detecte}] : {score_bonus}/20 pts | "
            f"{len(alertes)} diagnostic(s)"
        )

    return {
        "score_bonus":  score_bonus,
        "alertes":      alertes,
        "format":       format_detecte,
        "nb_controles": len(alertes),
    }
