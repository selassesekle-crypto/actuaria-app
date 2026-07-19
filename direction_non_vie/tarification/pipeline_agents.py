"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — ORCHESTRATEUR DU CHEMIN AGENT : LES TROIS CIBLES DU TARIF        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  A1 → A2 → A3, puis TROIS arbitrages complets — un par cible :               ║
║                                                                              ║
║    FRÉQUENCE  : A4(freq) → A5(freq, CANN+TabNet) → A6(freq)                  ║
║    COÛT       : A4(cout_moyen, sinistrés, sans poids)                        ║
║                 → A5(cout_moyen, TabNet SEUL) → A6(cout_moyen)               ║
║    PRIME PURE : A4(prime_pure, portefeuille ENTIER, sans poids)              ║
║                 → A5(prime_pure, TabNet SEUL) → A6(prime_pure)               ║
║                                                                              ║
║  POURQUOI CE MODULE EXISTE                                                   ║
║  ─────────────────────────                                                   ║
║  La prime pure est fréquence × coût. Or A4 et A5 ne s'entraînaient QUE sur   ║
║  la fréquence : sur la cible coût, A6 n'avait qu'un seul candidat (le GLM    ║
║  Gamma d'A3) et « l'arbitrait » contre personne. LA MOITIÉ DU TARIF N'ÉTAIT  ║
║  JAMAIS CHALLENGÉE. Constaté en re-vérifiant décennale : classement coût =   ║
║  1 ligne, 10 modèles écartés (à raison — ils déclaraient la fréquence).      ║
║                                                                              ║
║  Aucun orchestrateur n'existait : chaque appelant (app, demos, tests)        ║
║  assemblait la chaîne à la main — et `result_a5` valait `None` PARTOUT dans  ║
║  le dépôt : A5 n'était jamais câblé dans A6.                                 ║
║                                                                              ║
║  POURQUOI PAS AILLEURS                                                       ║
║  ─────────────────────                                                       ║
║  · Pas A6 : c'est un ARBITRE. Lui faire déclencher des entraînements         ║
║    inverserait les rôles et le rendrait intestable en isolation.             ║
║  · Pas pipeline_complet : c'est le chemin DÉCLARATIF (GLM pur), qui ne       ║
║    référence ni A4 ni A5. Autre architecture, autre objet.                   ║
║                                                                              ║
║  TROIS RÈGLES NON NÉGOCIABLES (décisions actuaires)                          ║
║  ──────────────────────────────────────────────────                          ║
║  1. Le sous-échantillon sinistrés vient de construire_cible_severite()       ║
║     (core/severite.py) — la SOURCE UNIQUE. On ne recalcule JAMAIS le masque  ║
║     ici : c'est cette duplication qui avait fait diverger A3 du déclaratif   ║
║     et sous-tarifer de 15 % (cf. 25f5711).                                   ║
║  2. CANN EXCLU de la cible coût. Son architecture est                        ║
║     exp(GLM_gelé(x) + offset·log(exposition)) : un modèle de COMPTAGE. La    ║
║     sévérité ne varie pas avec l'exposition — c'est le sens même de la       ║
║     décomposition E[S] = E[N] × E[C|N>0]. A5 reçoit modeles=('tabnet',).     ║
║  3. AUCUN POIDS sur la cible coût pour A4. L'exposition pondère un COMPTAGE, ║
║     pas une sévérité. Aligné sur pipeline_complet, qui ne pondère pas non    ║
║     plus son GLM de coût.                                                    ║
║                                                                              ║
║  AUTEUR    : ActuarIA                                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from core.plan_tarifaire import PlanTarifaire
from core.severite import construire_cible_severite
from direction_non_vie.tarification.a1_ingestion.agent import AgentA1Ingestion
from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
from direction_non_vie.tarification.a3_glm.agent import AgentA3GLM
from direction_non_vie.tarification.a4_ml.agent import AgentA4ML
from direction_non_vie.tarification.a5_deep_learning.agent import AgentA5DeepLearning
from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison

__all__ = ["ArbitrageCible", "ResultatAgents", "pipeline_agents", "CIBLE_COUT",
           "CIBLE_PRIME_PURE"]

# Nom de la cible de sévérité. DOIT être exactement celui que le GLM Gamma d'A3
# déclare (metriques['gamma']['cible']) : c'est sur cette chaîne que le filtre de
# cible d'A6 apparie les modèles. Une divergence ici et le Gamma serait écarté de
# son propre arbitrage.
CIBLE_COUT = "cout_moyen"

# Nom de la cible de PRIME PURE DIRECTE. DOIT être exactement celui que le GLM
# Tweedie d'A3 déclare (metriques['tweedie']['cible']='prime_pure') ET la colonne
# que A2 produit (_calculer_prime_pure : cout_total/expo, taux annualisé, HORS
# plan). Même contrat d'appariement de cible côté A6 que CIBLE_COUT.
CIBLE_PRIME_PURE = "prime_pure"


@dataclass(frozen=True)
class ArbitrageCible:
    """Un arbitrage complet, pour UNE cible."""
    cible:      str
    a4:         Optional[Dict[str, Any]]
    a5:         Optional[Dict[str, Any]]
    a6:         Optional[Dict[str, Any]]
    statut_rag: Optional[str]
    n_candidats: int          # modèles réellement en compétition
    erreur:     Optional[str] = None


@dataclass(frozen=True)
class ResultatAgents:
    """Les TROIS cibles du tarif, dans un objet unique : FRÉQUENCE et COÛT (dont
    le produit = prime pure par décomposition E[S]=E[N]×E[C|N>0]), et la PRIME
    PURE DIRECTE (route alternative Tweedie sur tout le portefeuille). Le tarif
    primaire reste fréquence×coût ; la prime pure directe est un CHALLENGEUR
    additif (d'où `.success` qui ne dépend que d'A3 + fréquence)."""
    plan:       PlanTarifaire
    a1:         Dict[str, Any]
    a2:         Dict[str, Any]
    a3:         Dict[str, Any]
    frequence:  ArbitrageCible
    cout:       ArbitrageCible
    prime_pure: ArbitrageCible
    audit_id:   str

    @property
    def success(self) -> bool:
        return bool(self.a3.get("success")) and self.frequence.a6 is not None

    def resume(self) -> Dict[str, Any]:
        """Vue JSON-SÉRIALISABLE des deux arbitrages — le livrable d'audit.

        Même contrat que tarifer() : 100 % types natifs, json.dumps() ne lève
        jamais, y compris sur un échec. Les objets lourds (dataframes, modèles
        sklearn/torch, bytes Excel) restent dans ResultatAgents mais N'ENTRENT PAS
        ici : ce résumé est fait pour être TRACÉ et TRANSMIS, pas pour rejouer le
        pipeline. C'est pourquoi ResultatAgents lui-même n'est pas sérialisable —
        et n'a pas à l'être : il porte de quoi travailler, resume() de quoi rendre
        compte.
        """
        def _f(x):
            return float(x) if isinstance(x, (int, float, np.floating)) else None

        def _arb(a: "ArbitrageCible") -> Dict[str, Any]:
            r6 = a.a6 or {}
            return {
                "cible":       a.cible,
                "statut_rag":  a.statut_rag,
                "n_candidats": int(a.n_candidats),
                "erreur":      a.erreur,
                "modele_production": (r6.get("modele_production") or {}).get("modele"),
                "classement": [
                    {"modele":   str(c.get("modele")),
                     "famille":  str(c.get("famille")),
                     "cible":    str(c.get("cible")),
                     "gini_test":    _f(c.get("gini_test")),
                     "score_global": _f(c.get("score_global"))}
                    for c in (r6.get("classement") or [])
                ],
                "exclusions_cible": [
                    {"modele":       str(e.get("modele")),
                     "cible_modele": str(e.get("cible_modele")),
                     "raison":       str(e.get("raison"))}
                    for e in (r6.get("exclusions_cible") or [])
                ],
                "alertes_modele": [str(x.get("code"))
                                   for x in (r6.get("alertes_modele") or [])],
            }

        return {
            "success":        bool(self.success),
            "audit_id":       self.audit_id,
            "date_calcul":    datetime.now().isoformat(),
            "plan_lob":       self.plan.lob,
            "plan_empreinte": self.plan.empreinte(),
            "frequence":      _arb(self.frequence),
            "cout":           _arb(self.cout),
            "prime_pure":     _arb(self.prime_pure),
        }


def _vue_sinistres(result_a2: Dict[str, Any], plan: PlanTarifaire) -> Dict[str, Any]:
    """Vue SINISTRÉS de result_a2, prête pour un entraînement sur la sévérité.

    Le masque, l'écrêtement et la cible viennent de construire_cible_severite() —
    la SOURCE UNIQUE, la même qu'A3 et pipeline_complet. On ne recalcule rien :
    dupliquer cette définition est exactement ce qui avait fait diverger les deux
    chemins (A3 ajustait le coût TOTAL en l'appelant 'cout_moyen', −15 % de tarif).

    Retourne un result_a2 de MÊME FORME, dont le dataframe est restreint aux
    contrats à coût observé et porte la colonne `CIBLE_COUT` (coût par sinistre,
    écrêté). A4/A5 peuvent alors l'utiliser sans savoir comment elle est faite.
    """
    df = result_a2["dataframe"]
    cible = construire_cible_severite(
        df[plan.cible_cout], df[plan.cible_frequence], df[plan.exposition])
    df_sin = df[cible.masque].copy().reset_index(drop=True)
    df_sin[CIBLE_COUT] = cible.severite
    return {**result_a2, "dataframe": df_sin}, cible


def _n_candidats(r6: Optional[Dict[str, Any]]) -> int:
    return len((r6 or {}).get("classement") or [])


def pipeline_agents(
    dataframe: pd.DataFrame,
    plan: PlanTarifaire,
    sous_branche: str,
    *,
    branche: str = "non_vie",
    environnement: str = "production",
    profil_valide_par: Optional[str] = None,
    valide_par_actuaire_dl: Optional[str] = None,
    rapport_mapping: Optional[Any] = None,
    n_epochs_dl: int = 200,
    batch_size_dl: int = 512,
    calcul_shap: bool = True,
    generer_graphiques: bool = False,
    models_path: str = "/tmp",
    audit_path: str = "/tmp",
    verbose: bool = False,
) -> ResultatAgents:
    """Enchaîne A1→A6 sur les TROIS cibles et rend les trois arbitrages.

    `sous_branche` est DÉCLARÉE (A1 ne devine plus la LoB) ; `plan` est le plan
    signé, autorité de bout en bout. Les agents DL/ML sont appelés TROIS FOIS —
    une fois par cible — plutôt que refactorés en multi-cibles : A6 arbitre déjà
    une cible par appel, et le résultat de chaque agent porte UNE `col_cible`
    que le filtre de cible d'A6 apparie. Le grain existant est le bon.

    Un arbitrage peut échouer là où un autre réussit (COÛT : trop peu de
    sinistres ; PRIME PURE : donnée dégénérée) : c'est rendu dans `<cible>.erreur`,
    jamais masqué, et n'empêche pas les autres d'aboutir. `.success` ne dépend que
    d'A3 + fréquence (le tarif primaire reste fréquence×coût).
    """
    t0 = datetime.now()
    audit_id = f"AGENTS_{t0.strftime('%Y%m%d_%H%M%S')}"
    _a = dict(models_path=models_path, audit_path=audit_path, verbose=verbose)

    # ── SOCLE COMMUN : A1 → A2 → A3 ─────────────────────────────────────────
    r1 = AgentA1Ingestion(audit_path=audit_path, verbose=verbose).run(
        branche=branche, sous_branche=sous_branche, dataframe=dataframe)
    r2 = AgentA2Preprocessing(audit_path=audit_path, verbose=verbose).run(
        result_a1=r1, plan=plan)
    # A3 entraîne DÉJÀ ses trois modèles (Poisson fréquence, Gamma coût, Tweedie
    # prime pure) en un seul run : c'est son architecture, on ne la double pas.
    r3 = AgentA3GLM(**_a).run(
        result_a2=r2, plan=plan,
        col_frequence=plan.cible_frequence, col_cout=plan.cible_cout,
        generer_graphiques=generer_graphiques)

    def _echec(cible: str, msg: str) -> ArbitrageCible:
        return ArbitrageCible(cible=cible, a4=None, a5=None, a6=None,
                              statut_rag=None, n_candidats=0, erreur=msg)

    if not r3.get("success"):
        msg = f"A3 a échoué : {r3.get('erreur')}"
        return ResultatAgents(plan=plan, a1=r1, a2=r2, a3=r3,
                              frequence=_echec(plan.cible_frequence, msg),
                              cout=_echec(CIBLE_COUT, msg),
                              prime_pure=_echec(CIBLE_PRIME_PURE, msg),
                              audit_id=audit_id)

    def _arbitrer(cible, r2_cible, *, modeles_dl, ponderer) -> ArbitrageCible:
        """Une cible : A4 → A5 → A6. Les échecs sont rendus, jamais masqués."""
        r4 = AgentA4ML(**_a).run(
            result_a2=r2_cible, result_a3=r3, plan=plan, col_cible=cible,
            ponderer_par_exposition=ponderer, calcul_shap=calcul_shap,
            generer_graphiques=generer_graphiques)
        r5 = AgentA5DeepLearning(**_a).run(
            result_a2=r2_cible, result_a3=r3, result_a4=r4, plan=plan,
            col_cible=cible, modeles=modeles_dl, n_epochs=n_epochs_dl,
            batch_size=batch_size_dl, generer_graphiques=generer_graphiques)
        r6 = AgentA6Comparaison(**_a).run(
            result_a2=r2_cible, result_a3=r3, result_a4=r4,
            result_a5=r5 if r5.get("success") else None,
            col_cible=cible, plan=plan, environnement=environnement,
            profil_valide_par=profil_valide_par,
            valide_par_actuaire_dl=valide_par_actuaire_dl,
            rapport_mapping=rapport_mapping,
            generer_graphiques=generer_graphiques, generer_rapport_equipe=False)
        return ArbitrageCible(cible=cible, a4=r4, a5=r5, a6=r6,
                              statut_rag=r6.get("statut_rag"),
                              n_candidats=_n_candidats(r6))

    # ── CIBLE 1 : FRÉQUENCE — le portefeuille entier, pondéré par l'exposition ─
    frequence = _arbitrer(plan.cible_frequence, r2,
                          modeles_dl=("cann", "tabnet"), ponderer=True)

    # ── CIBLE 2 : COÛT — sinistrés seulement, sans poids, TabNet seul ────────
    try:
        r2_cout, cible_sev = _vue_sinistres(r2, plan)
    except Exception as e:      # pragma: no cover — donnée dégénérée
        cout = _echec(CIBLE_COUT, f"Vue sinistrés impossible : {type(e).__name__}: {e}")
    else:
        if cible_sev.n_retenus < 100:
            # On ne bricole pas un modèle sur trois sinistres : on le DIT.
            cout = _echec(
                CIBLE_COUT,
                f"Sévérité non modélisable : {cible_sev.n_retenus} contrat(s) à "
                f"coût observé (< 100). Le GLM Gamma d'A3 reste la référence.")
        else:
            cout = _arbitrer(CIBLE_COUT, r2_cout,
                             modeles_dl=("tabnet",), ponderer=False)

    # ── CIBLE 3 : PRIME PURE DIRECTE — portefeuille ENTIER, sans poids, TabNet ─
    # La prime pure (cout/expo, taux annualisé produit par A2 HORS plan) est une
    # cible Tweedie : masse en 0 (non-sinistrés) + queue. On l'entraîne sur TOUT
    # le portefeuille — PAS la vue sinistrés : ici la masse en 0 EST le signal
    # (fréquence × sévérité en un seul modèle). ponderer=False : la cible est déjà
    # annualisée, donc exposure-INDÉPENDANTE (même raison qui exclut le CANN, dont
    # l'offset log-expo est une construction de comptage). Concurrent GLM = le
    # Tweedie d'A3 (cible='prime_pure'). PAS de seuil <100 : le portefeuille entier
    # fournit toujours des lignes ; le signal (fonction du nombre de sinistrés) est
    # évalué par le RAG d'A6. Enveloppé comme le coût : un échec est DIT, pas masqué.
    if CIBLE_PRIME_PURE not in r2["dataframe"].columns:
        prime_pure = _echec(
            CIBLE_PRIME_PURE,
            f"Colonne '{CIBLE_PRIME_PURE}' absente d'A2 (contrat de données V7 B2 "
            f"rompu — _calculer_prime_pure).")
    else:
        try:
            prime_pure = _arbitrer(CIBLE_PRIME_PURE, r2,
                                   modeles_dl=("tabnet",), ponderer=False)
        except Exception as e:      # pragma: no cover — donnée dégénérée
            prime_pure = _echec(
                CIBLE_PRIME_PURE,
                f"Prime pure non modélisable : {type(e).__name__}: {e}")

    return ResultatAgents(plan=plan, a1=r1, a2=r2, a3=r3,
                          frequence=frequence, cout=cout,
                          prime_pure=prime_pure, audit_id=audit_id)
