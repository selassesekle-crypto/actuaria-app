# =============================================================================
#  ActuarIA — Direction Non-Vie
#  nv_triangle_diagnostics.py — Diagnostic qualité du triangle
# =============================================================================
#
#  Module autonome appelé par NVTriangleBuilder avant tout calcul A7.
#  Produit un score de santé sur 100 avec 7 contrôles structurés.
#
#  Score :  ≥ 85 → VERT   (triangle de bonne qualité)
#           70-84 → AMBRE  (anomalies mineures, calculs possibles avec prudence)
#           < 70  → ROUGE  (anomalies significatives, résultats à interpréter
#                           avec précaution)
#
#  Contrôles :
#    C1 — Monotonie cumulée       (15 pts) : valeurs croissantes sur les lignes
#    C2 — Diagonales manquantes   (15 pts) : pas de diagonale entièrement vide
#    C3 — Trous internes          (15 pts) : pas de zéro dans la zone observée
#    C4 — Dimensions suffisantes  (15 pts) : n_années ≥ 5
#    C5 — Valeurs aberrantes      (15 pts) : facteurs dans [0.5 × médiane, 3 × médiane]
#    C6 — Cohérence diagonale     (15 pts) : dernière diagonale croissante
#    C7 — Taux de remplissage     (10 pts) : > 30% des cellules attendues remplies
#
# =============================================================================

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger('actuaria.diagnostics')


def _verdict_cumulativite(C: np.ndarray) -> str:
    """'cumule' | 'incremental' | 'ambigu' — délégué à la SOURCE UNIQUE.

    `detecter_cumulativite` (nv_triangle_construction) porte déjà cette logique à
    trois états ; la recopier ici recréerait exactement le risque de dérive qu'on
    a éliminé ailleurs. Import DIFFÉRÉ : ce module reste importable seul (il n'a
    besoin que de numpy), et un environnement sans le module de construction
    dégrade proprement en 'ambigu' — le cas prudent, qui n'accuse jamais à tort.
    """
    try:
        from direction_non_vie.services.nv_triangle_construction import (
            detecter_cumulativite,
        )
    except Exception as e:                      # dégradation propre, jamais un crash
        logger.warning("detecter_cumulativite indisponible (%s) — verdict 'ambigu'.", e)
        return 'ambigu'
    return detecter_cumulativite(C)


def diagnostiquer_triangle(
    C           : np.ndarray,
    annee_debut : Optional[int] = None,
    lob         : str = 'generique',
) -> Dict:
    """
    Calcule le score de santé du triangle et retourne un rapport structuré.

    Parameters
    ----------
    C           : np.ndarray — triangle cumulé (n×m), zéros pour cellules futures
    annee_debut : int, optional — première année de survenance (pour les labels)
    lob         : str — ligne de branche (pour seuils spécifiques)

    Returns
    -------
    dict :
        score          : int — score global sur 100
        statut         : str — 'VERT' | 'AMBRE' | 'ROUGE'
        controles      : list — détail des 7 contrôles
        recommandations: list — actions prioritaires
        resume         : str — synthèse narrative
    """
    if C is None or not hasattr(C, 'shape') or C.ndim != 2:
        return _score_invalide("Triangle invalide ou absent")

    n, m = C.shape

    if n < 2 or m < 2:
        return _score_invalide(f"Triangle trop petit ({n}×{m}) — minimum 2×2")

    controles = []
    score_total = 0

    # ── C1 — MONOTONIE CUMULÉE ───────────────────────────────────────────────
    c1 = _ctrl_monotonie(C, n, m, annee_debut)
    controles.append(c1)
    score_total += c1['points']

    # ── C2 — DIAGONALES MANQUANTES ───────────────────────────────────────────
    c2 = _ctrl_diagonales_manquantes(C, n, m, annee_debut)
    controles.append(c2)
    score_total += c2['points']

    # ── C3 — TROUS INTERNES ──────────────────────────────────────────────────
    c3 = _ctrl_trous_internes(C, n, m)
    controles.append(c3)
    score_total += c3['points']

    # ── C4 — DIMENSIONS SUFFISANTES ──────────────────────────────────────────
    c4 = _ctrl_dimensions(C, n, m, lob)
    controles.append(c4)
    score_total += c4['points']

    # ── C5 — VALEURS ABERRANTES ───────────────────────────────────────────────
    c5 = _ctrl_valeurs_aberrantes(C, n, m)
    controles.append(c5)
    score_total += c5['points']

    # ── C6 — COHÉRENCE DIAGONALE ──────────────────────────────────────────────
    c6 = _ctrl_coherence_diagonale(C, n, m, annee_debut)
    controles.append(c6)
    score_total += c6['points']

    # ── C7 — TAUX DE REMPLISSAGE ──────────────────────────────────────────────
    c7 = _ctrl_remplissage(C, n, m)
    controles.append(c7)
    score_total += c7['points']

    # ── STATUT GLOBAL ─────────────────────────────────────────────────────────
    statut = 'VERT' if score_total >= 85 else 'AMBRE' if score_total >= 70 else 'ROUGE'

    # ── RECOMMANDATIONS ───────────────────────────────────────────────────────
    recommandations = _generer_recommandations(controles, n, m, lob)

    # ── RÉSUMÉ NARRATIF ───────────────────────────────────────────────────────
    n_ok    = sum(1 for c in controles if c['statut'] == 'VERT')
    n_ambre = sum(1 for c in controles if c['statut'] == 'AMBRE')
    n_rouge = sum(1 for c in controles if c['statut'] == 'ROUGE')

    resume = _generer_resume(score_total, statut, n, m, n_ok, n_ambre, n_rouge, lob)

    return {
        'score'          : score_total,
        'statut'         : statut,
        'controles'      : controles,
        'recommandations': recommandations,
        'resume'         : resume,
        'dimensions'     : f"{n}×{m}",
        'n_annees'       : n,
        'n_periodes'     : m,
    }


# =============================================================================
#  CONTRÔLES INDIVIDUELS
# =============================================================================

def _ctrl_monotonie(C, n, m, annee_debut) -> Dict:
    """C1 — Les valeurs cumulées décroissent-elles, et si oui pourquoi ?

    Le VERDICT est délégué à detecter_cumulativite() (module de construction) —
    SOURCE UNIQUE de cette logique, jamais recopiée ici. Ce contrôle n'ajoute que
    l'énumération cellule par cellule, qui est un besoin d'affichage propre au
    diagnostic.

    Trois cas, là où l'ancienne version n'en voyait qu'un :
      · 'cumule'      → VERT   : rien ne décroît au-delà du bruit d'arrondi.
      · 'ambigu'      → AMBRE  : décroissances MODÉRÉES ou PARTIELLES — signature
                        d'un RECOURS / subrogation, parfaitement légitime sur un
                        cumulé (le chantier IBNR l'a établi pour toutes les
                        méthodes). L'ancienne version criait « vérifier le
                        format » et retirait 15 points à une donnée SAINE : dès
                        2 % de recours elle comptait 24 violations sur un 10×10.
      · 'incremental' → ROUGE  : décroissances FORTES et GÉNÉRALISÉES avec
                        première colonne dominante — le triangle ressemble à des
                        incréments bruts, c'est-à-dire une vraie erreur de format.
    """
    pts_max = 15
    violations = []

    for i in range(n):
        for j in range(1, m):
            # Zone future : i + j >= n pour un triangle carré
            # OU deux zéros consécutifs = fin des données
            if i + j >= n:
                break
            if C[i, j] == 0 and (j+1 >= m or C[i, j+1] == 0):
                break  # fin réelle des données
            if C[i, j] > 0 and C[i, j-1] > 0 and C[i, j] < C[i, j-1] * 0.99:
                an = (annee_debut + i) if annee_debut else i
                violations.append(f"Ligne {an} col {j+1}: {C[i,j]:,.0f} < {C[i,j-1]:,.0f}")

    if not violations:
        return {
            'code': 'C1', 'libelle': 'Monotonie cumulée',
            'statut': 'VERT', 'points': pts_max,
            'message': f"✅ Toutes les lignes sont croissantes — triangle cumulé cohérent.",
            'detail': [],
        }

    if _verdict_cumulativite(C) == 'incremental':
        return {
            'code': 'C1', 'libelle': 'Monotonie cumulée',
            'statut': 'ROUGE', 'points': 0,
            'message': (f"🔴 {len(violations)} décroissances fortes et généralisées — "
                        f"le triangle ressemble à des INCRÉMENTS bruts. Vérifier le "
                        f"format (cumulé vs incrémental) avant tout calcul."),
            'detail': violations[:5],
        }

    return {
        'code': 'C1', 'libelle': 'Monotonie cumulée',
        'statut': 'AMBRE', 'points': 12,
        'message': (f"⚠️ {len(violations)} décroissance(s) modérée(s) — cohérent avec "
                    f"un RECOURS / subrogation légitime sur un triangle cumulé. "
                    f"À confirmer si ce n'était pas attendu."),
        'detail': violations[:5],
    }


def _ctrl_diagonales_manquantes(C, n, m, annee_debut) -> Dict:
    """C2 — Pas de diagonale entièrement vide dans la zone observée."""
    pts_max = 15
    diag_vides = []

    # La diagonale k correspond à la période de développement j = n-1-i+k
    # On vérifie les colonnes complètes dans la zone observée
    for j in range(m):
        # Zone observable : toutes les lignes i où la cellule peut avoir une valeur
        # Pour triangle carré : i + j < n. Pour rectangulaire : toutes les lignes
        col_vals = [
            C[i, j] for i in range(n)
            if i + j < n or (m > n and j < m - n + i)
        ]
        # Simplification robuste : colonne vide si TOUTES les valeurs de la colonne = 0
        col_all = [C[i, j] for i in range(n)]
        if col_all and all(v == 0 for v in col_all):
            diag_vides.append(f"Colonne {j+1} entièrement vide")

    if not diag_vides:
        return {
            'code': 'C2', 'libelle': 'Diagonales manquantes',
            'statut': 'VERT', 'points': pts_max,
            'message': "✅ Aucune diagonale manquante détectée.",
            'detail': [],
        }
    elif len(diag_vides) == 1:
        return {
            'code': 'C2', 'libelle': 'Diagonales manquantes',
            'statut': 'AMBRE', 'points': 7,
            'message': f"⚠️ 1 colonne vide — possible changement d'exercice fiscal ou données manquantes.",
            'detail': diag_vides,
        }
    else:
        return {
            'code': 'C2', 'libelle': 'Diagonales manquantes',
            'statut': 'ROUGE', 'points': 0,
            'message': f"🔴 {len(diag_vides)} colonnes vides — structure du triangle à vérifier.",
            'detail': diag_vides,
        }


def _ctrl_trous_internes(C, n, m) -> Dict:
    """C3 — Pas de zéro dans la zone observée (hors zone future)."""
    pts_max = 15
    trous = []

    for i in range(n):
        for j in range(m):
            if i + j >= n:
                break  # zone future
            if C[i, j] == 0 and j > 0:
                # Zéro dans la zone observée mais pas en première colonne
                if C[i, j-1] > 0:  # la cellule précédente est remplie
                    trous.append(f"Ligne {i+1}, col {j+1}")

    if not trous:
        return {
            'code': 'C3', 'libelle': 'Trous internes',
            'statut': 'VERT', 'points': pts_max,
            'message': "✅ Aucun trou interne — triangle continu.",
            'detail': [],
        }
    elif len(trous) <= 3:
        return {
            'code': 'C3', 'libelle': 'Trous internes',
            'statut': 'AMBRE', 'points': 7,
            'message': f"⚠️ {len(trous)} trou(s) interne(s) — peut indiquer des sinistres à zéro ou données manquantes.",
            'detail': trous[:5],
        }
    else:
        return {
            'code': 'C3', 'libelle': 'Trous internes',
            'statut': 'ROUGE', 'points': 0,
            'message': f"🔴 {len(trous)} trous internes — triangle incomplet, résultats peu fiables.",
            'detail': trous[:5],
        }


def _ctrl_dimensions(C, n, m, lob) -> Dict:
    """C4 — Dimensions minimales selon la branche."""
    pts_max = 15

    # Seuils par branche (années minimales recommandées)
    seuils = {
        'rc_medicale':      (15, 20),
        'construction':     (12, 15),
        'rc_auto_corporels':(12, 15),
        'rc_generale':      (8,  12),
        'rc_auto_materiel': (6,  10),
        'mrh':              (5,   8),
    }
    min_warn, min_ok = seuils.get(lob, (5, 8))

    if n >= min_ok:
        return {
            'code': 'C4', 'libelle': 'Dimensions suffisantes',
            'statut': 'VERT', 'points': pts_max,
            'message': f"✅ {n} années × {m} périodes — triangle de taille satisfaisante pour la branche.",
            'detail': [],
        }
    elif n >= min_warn:
        return {
            'code': 'C4', 'libelle': 'Dimensions suffisantes',
            'statut': 'AMBRE', 'points': 8,
            'message': (f"⚠️ {n} années — en dessous de l'optimum ({min_ok} ans) pour cette branche. "
                       f"BF recommandé sur les dernières cohortes."),
            'detail': [],
        }
    else:
        return {
            'code': 'C4', 'libelle': 'Dimensions suffisantes',
            'statut': 'ROUGE', 'points': 0,
            'message': (f"🔴 {n} années seulement — triangle trop court pour cette branche "
                       f"(minimum recommandé : {min_warn} ans). Résultats indicatifs uniquement."),
            'detail': [],
        }


def _ctrl_valeurs_aberrantes(C, n, m) -> Dict:
    """C5 — Facteurs de développement dans une plage raisonnable."""
    pts_max = 15

    # Calculer les facteurs de développement colonne par colonne
    facteurs_aberrants = []
    all_facteurs = []

    for j in range(m - 1):
        col_facteurs = []
        for i in range(n):
            # Zone observable : i + j < n pour triangle carré
            # Pour triangles rectangulaires (m > n), on peut avoir des facteurs au-delà
            if i + j >= n and m <= n:
                break
            if j + 1 >= m:
                break
            if C[i, j] > 0 and C[i, j+1] > 0:
                f = C[i, j+1] / C[i, j]
                col_facteurs.append(f)

        if len(col_facteurs) >= 2:
            mediane = float(np.median(col_facteurs))
            all_facteurs.extend(col_facteurs)
            for idx, f in enumerate(col_facteurs):
                if f > 3 * mediane or f < mediane / 3:
                    facteurs_aberrants.append(
                        f"Col {j+1}→{j+2}, ligne {idx+1}: facteur {f:.3f} "
                        f"(médiane col = {mediane:.3f})"
                    )

    if not facteurs_aberrants:
        return {
            'code': 'C5', 'libelle': 'Valeurs aberrantes',
            'statut': 'VERT', 'points': pts_max,
            'message': "✅ Aucun facteur aberrant détecté — facteurs homogènes.",
            'detail': [],
        }
    elif len(facteurs_aberrants) <= 2:
        return {
            'code': 'C5', 'libelle': 'Valeurs aberrantes',
            'statut': 'AMBRE', 'points': 7,
            'message': f"⚠️ {len(facteurs_aberrants)} facteur(s) atypique(s) — à investiguer (sinistre exceptionnel ?).",
            'detail': facteurs_aberrants[:3],
        }
    else:
        return {
            'code': 'C5', 'libelle': 'Valeurs aberrantes',
            'statut': 'ROUGE', 'points': 0,
            'message': f"🔴 {len(facteurs_aberrants)} facteurs aberrants — hétérogénéité forte, CL peu fiable.",
            'detail': facteurs_aberrants[:5],
        }


def _ctrl_coherence_diagonale(C, n, m, annee_debut) -> Dict:
    """C6 — La dernière diagonale (sinistres les plus récents) est globalement croissante."""
    pts_max = 15

    # Extraire la dernière diagonale observée
    diag = []
    for i in range(n):
        j = n - 1 - i  # index colonne sur la diagonale principale
        if j < m and C[i, j] > 0:
            diag.append((i, j, float(C[i, j])))

    if len(diag) < 3:
        return {
            'code': 'C6', 'libelle': 'Cohérence diagonale',
            'statut': 'AMBRE', 'points': 8,
            'message': "⚠️ Diagonale trop courte pour analyse de cohérence (< 3 points).",
            'detail': [],
        }

    # Vérifier que les montants sont globalement décroissants avec l'ancienneté
    # (les cohortes les plus récentes ont moins de développement → montants plus faibles)
    montants = [d[2] for d in diag]
    # On s'attend à ce que les premières cohortes (plus matures) aient des montants plus élevés
    # Sur la diagonale : cohortes anciennes (i=0) ont montants élevés (développées)
    # cohortes récentes (i=n-1) ont montants faibles (peu développées)
    # Une 'inversion forte' = une cohorte récente a un montant >> cohorte ancienne
    # ce qui serait anormal sauf si sinistre catastrophique récent
    inversions = sum(
        1 for k in range(len(montants)-1)
        if montants[k+1] > montants[k] * 2.0  # cohorte récente 2x supérieure à l'ancienne
    )

    if inversions == 0:
        return {
            'code': 'C6', 'libelle': 'Cohérence diagonale',
            'statut': 'VERT', 'points': pts_max,
            'message': "✅ Dernière diagonale cohérente — progression attendue des montants cumulés.",
            'detail': [],
        }
    elif inversions <= 1:
        return {
            'code': 'C6', 'libelle': 'Cohérence diagonale',
            'statut': 'AMBRE', 'points': 8,
            'message': f"⚠️ {inversions} inversion sur la diagonale — à vérifier (sinistre exceptionnel ?).",
            'detail': [],
        }
    else:
        return {
            'code': 'C6', 'libelle': 'Cohérence diagonale',
            'statut': 'ROUGE', 'points': 0,
            'message': f"🔴 {inversions} inversions sur la diagonale — incohérence structurelle à analyser.",
            'detail': [],
        }


def _ctrl_remplissage(C, n, m) -> Dict:
    """C7 — Taux de remplissage de la zone observable."""
    pts_max = 10

    # Zone observable = triangle supérieur gauche
    n_attendu = n * (n + 1) // 2  # triangle carré attendu
    n_rempli  = sum(1 for i in range(n) for j in range(m)
                    if i + j < n and C[i, j] > 0)
    taux = n_rempli / n_attendu * 100 if n_attendu > 0 else 0

    if taux >= 80:
        return {
            'code': 'C7', 'libelle': 'Taux de remplissage',
            'statut': 'VERT', 'points': pts_max,
            'message': f"✅ {taux:.1f}% des cellules attendues remplies — triangle dense.",
            'detail': [],
        }
    elif taux >= 50:
        return {
            'code': 'C7', 'libelle': 'Taux de remplissage',
            'statut': 'AMBRE', 'points': 5,
            'message': f"⚠️ {taux:.1f}% de remplissage — triangle partiellement vide, prudence sur les facteurs.",
            'detail': [],
        }
    else:
        return {
            'code': 'C7', 'libelle': 'Taux de remplissage',
            'statut': 'ROUGE', 'points': 0,
            'message': f"🔴 {taux:.1f}% seulement — triangle très creux, résultats peu fiables.",
            'detail': [],
        }


# =============================================================================
#  RECOMMANDATIONS ET RÉSUMÉ
# =============================================================================

def _generer_recommandations(controles: List[Dict], n: int, m: int, lob: str) -> List[str]:
    """Génère les recommandations prioritaires selon les contrôles."""
    recs = []

    for c in controles:
        if c['statut'] == 'ROUGE':
            if c['code'] == 'C1':
                recs.append("🔴 PRIORITAIRE — Vérifier que votre fichier est bien un triangle CUMULÉ (Format A). "
                           "Si c'est un triangle incrémental, sélectionnez le Format B.")
            elif c['code'] == 'C2':
                recs.append("🔴 PRIORITAIRE — Des colonnes entièrement vides ont été détectées. "
                           "Vérifier si un changement d'exercice fiscal ou une interruption de données explique ces trous.")
            elif c['code'] == 'C3':
                recs.append("🔴 PRIORITAIRE — Des trous internes sont présents. "
                           "Contacter le service de gestion des sinistres pour obtenir les données manquantes.")
            elif c['code'] == 'C4':
                recs.append(f"🔴 PRIORITAIRE — Triangle trop court ({n} ans). "
                           "Utiliser BF avec a priori externe sur toutes les cohortes. "
                           "Ne pas inscrire le BE au bilan S2 sans validation de l'actuaire désigné.")
            elif c['code'] == 'C5':
                recs.append("🔴 PRIORITAIRE — Facteurs aberrants détectés. "
                           "Identifier les sinistres exceptionnels (CAT NAT, sinistres sériels) "
                           "et les isoler avant recalcul (Large Loss Threshold recommandé).")
            elif c['code'] == 'C6':
                recs.append("🔴 PRIORITAIRE — Incohérence sur la dernière diagonale. "
                           "Vérifier l'ordre des années de survenance et la date d'arrêté.")
            elif c['code'] == 'C7':
                recs.append("🔴 PRIORITAIRE — Triangle trop creux. "
                           "BF obligatoire sur les cohortes récentes. "
                           "Fournir les données manquantes avant tout calcul S2.")

        elif c['statut'] == 'AMBRE':
            if c['code'] == 'C4':
                recs.append(f"⚠️ Triangle court ({n} ans) — BF recommandé sur les 3 dernières cohortes.")
            elif c['code'] == 'C5':
                recs.append("⚠️ Facteurs atypiques — documenter les années concernées dans le rapport actuariel.")
            elif c['code'] == 'C2':
                recs.append("⚠️ Colonne manquante — vérifier la continuité des données sur cette période.")

    if not recs:
        recs.append("✅ Triangle de bonne qualité — aucune action correctrice requise avant calcul.")

    return recs


def _generer_resume(score, statut, n, m, n_ok, n_ambre, n_rouge, lob) -> str:
    """Génère un résumé narratif du diagnostic."""
    emoji = "✅" if statut == "VERT" else "⚠️" if statut == "AMBRE" else "🔴"

    intro = (
        f"{emoji} Le triangle {n}×{m} obtient un score de qualité de {score}/100 "
        f"({n_ok}/7 contrôles VERT, {n_ambre} AMBRE, {n_rouge} ROUGE). "
    )

    if statut == 'VERT':
        corps = ("Le triangle présente une qualité satisfaisante. "
                "Les calculs actuariels peuvent être lancés avec confiance. "
                "Les résultats sont directement utilisables pour le bilan S2.")
    elif statut == 'AMBRE':
        corps = ("Le triangle présente des anomalies mineures qui méritent attention. "
                "Les calculs restent possibles mais les résultats doivent être interprétés "
                "avec prudence. Documenter les points d'attention dans le rapport actuariel.")
    else:
        corps = ("Le triangle présente des anomalies significatives. "
                "Les résultats des méthodes actuarielles peuvent être biaisés. "
                "Il est fortement recommandé de corriger les anomalies avant tout calcul S2. "
                "Ne pas inscrire le BE au bilan sans validation de l'actuaire désigné.")

    return intro + corps


def _score_invalide(message: str) -> Dict:
    return {
        'score'          : 0,
        'statut'         : 'ROUGE',
        'controles'      : [],
        'recommandations': [f"🔴 {message}"],
        'resume'         : f"🔴 Diagnostic impossible : {message}",
        'dimensions'     : '—',
        'n_annees'       : 0,
        'n_periodes'     : 0,
    }
