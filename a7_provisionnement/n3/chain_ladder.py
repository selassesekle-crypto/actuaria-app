# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n3/chain_ladder.py  —  Méthode Chain Ladder (4 variantes + tail factor)
# =============================================================================
#
#  Références mathématiques
#  ------------------------
#  Mack (1993) — "Distribution-Free Calculation of the Standard Error
#                 of Chain Ladder Reserve Estimates"
#                 ASTIN Bulletin 23(2), pp. 213-225
#
#  Taylor (1986) — "Claims Reserving in Non-Life Insurance"
#                  North-Holland, Amsterdam
#
#  Formules implémentées
#  ----------------------
#
#  Facteurs de développement
#  ─────────────────────────
#  Zone connue : C[i,j] disponible si i + j < n  (triangle supérieur gauche)
#
#  Standard (volume-weighted, Mack 1993) :
#      f_j = Σ_{i : i+j+1 < n} C[i,j+1]
#            ─────────────────────────────
#            Σ_{i : i+j+1 < n} C[i,j]
#
#  Volume-weighted (pondération √C[i,j]) :
#      f_j = Σ_{i} √C[i,j] × f[i,j]
#            ────────────────────────
#            Σ_{i} √C[i,j]
#      avec f[i,j] = C[i,j+1] / C[i,j]
#
#  Médiane :
#      f_j = médiane { f[i,j] = C[i,j+1]/C[i,j] | i+j+1 < n, C[i,j]>0 }
#
#  Trimmed mean (écrêtée 10%-90%) :
#      f_j = moyenne de { f[i,j] | q10 ≤ f[i,j] ≤ q90 }
#
#  Facteurs cumulés (de la colonne j jusqu'à ultime) :
#      F_j = f_j × f_{j+1} × ... × f_{m-2} × tail
#      F_{m-1} = tail
#
#  Ultimates :
#      U_i = C[i, k_i] × f_{k_i} × f_{k_i+1} × ... × f_{m-2} × tail
#      où k_i = min(n-i-1, m-1) = dernière colonne connue pour l'année i
#
#  IBNR :
#      IBNR_i = max(U_i - C[i, k_i], 0)
#
#  Réserve totale :
#      R = Σ_{i=annee_base}^{n-1} IBNR_i
#      Par défaut annee_base=1 (l'année i=0 est supposée totalement développée)
#      Paramétrable via annee_base_reserve
#
#  Tail factor (régression log-linéaire)
#  ──────────────────────────────────────
#  Sur les k derniers facteurs (k=min(8, n_facteurs)) :
#      log(f_j - 1) = a + b × j    →    régression OLS
#      tail = Π_{j=m-1}^{∞} (1 + exp(a + b×j))  (tronqué à convergence)
#
#  Dimensions du triangle
#  ──────────────────────
#  n×m quelconque avec :
#    · n ≥ 3  (années de survenance)
#    · m ≥ 3  (périodes de développement)
#    · n×m    carré (cas standard) ou rectangulaire (triangle tronqué)
#    · Cas typique marché FR : 10×10 à 15×15
#    · Cas RC Médicale / Construction : 20×25 à 30×30
#    · Max supporté : 60×60 (validation N1)
#
# =============================================================================

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger('actuaria.a7')


# =============================================================================
#  CALCUL DES FACTEURS DE DÉVELOPPEMENT
# =============================================================================

def calculer_facteurs(
    C:       np.ndarray,
    methode: str = 'standard',
) -> Tuple[np.ndarray, List[List[float]]]:
    """
    Calcule les facteurs de développement CL et les facteurs individuels.

    Parameters
    ----------
    C : np.ndarray  shape (n, m)
        Triangle cumulé. Zone connue : C[i,j] avec i+j < n.
        Zéros utilisés pour les cellules inconnues (hors zone connue).
    methode : str
        'standard'        — volume-weighted (Mack 1993, estimateur optimal)
        'volume_weighted' — pondération par √C[i,j]
        'mediane'         — médiane des facteurs individuels (robuste outliers)
        'trimmed_mean'    — moyenne écrêtée 10%-90% (compromis)

    Returns
    -------
    facteurs : np.ndarray  shape (m-1,)
        Vecteur des facteurs agrégés f_0, ..., f_{m-2}.
        Tous ≥ 1.0 (un triangle cumulé ne peut que croître).
    facteurs_indiv : List[List[float]]
        facteurs_indiv[j] = liste des f[i,j] = C[i,j+1]/C[i,j]
        pour les i tels que i+j+1 < n et C[i,j] > 0.
        Utilisés par Mack (σ²) et Bootstrap ODP (résidus).
    """
    n, m         = C.shape
    facteurs     = np.ones(m - 1)
    facteurs_ind = []   # facteurs_ind[j] = [f[0,j], f[1,j], ...]

    for j in range(m - 1):
        f_ind = []   # facteurs individuels de la colonne j
        c_j   = []   # C[i,j] correspondants (pour pondérations)

        for i in range(n):
            # Zone connue : i+j < n  ET  i+j+1 < n
            if i + j + 1 >= n:
                break
            c_ij  = float(C[i, j])
            c_ij1 = float(C[i, j + 1])
            if c_ij > 0 and c_ij1 > 0:
                f_ind.append(c_ij1 / c_ij)
                c_j.append(c_ij)

        facteurs_ind.append(f_ind)

        if not f_ind:
            # Aucune observation → facteur = 1 (neutre)
            facteurs[j] = 1.0
            logger.warning(f"Colonne j={j} : aucune observation — facteur=1.0")
            continue

        arr = np.array(f_ind,  dtype=float)
        w   = np.array(c_j,    dtype=float)

        if methode in ('standard', 'volume_weighted') and methode == 'standard':
            # ── Standard (Mack 1993) ────────────────────────────────────────
            # f_j = Σ C[i,j+1] / Σ C[i,j]
            # Équivalent à np.average(arr, weights=w) car :
            # Σ w_i f_i / Σ w_i = Σ C[i,j]×(C[i,j+1]/C[i,j]) / Σ C[i,j]
            #                    = Σ C[i,j+1] / Σ C[i,j]
            facteurs[j] = float(np.average(arr, weights=w))

        elif methode == 'volume_weighted':
            # ── Volume-weighted (pondération √C[i,j]) ──────────────────────
            # Donne moins de poids aux très grandes années
            w_sqrt      = np.sqrt(w)
            facteurs[j] = float(np.average(arr, weights=w_sqrt))

        elif methode == 'mediane':
            # ── Médiane ─────────────────────────────────────────────────────
            # Insensible aux outliers. Perd l'information volume.
            facteurs[j] = float(np.median(arr))

        elif methode == 'trimmed_mean':
            # ── Moyenne écrêtée 10%-90% ─────────────────────────────────────
            # Élimine les 10% les plus hauts et les 10% les plus bas.
            # Nécessite au moins 4 observations pour être significative.
            if len(arr) >= 4:
                q10 = np.percentile(arr, 10)
                q90 = np.percentile(arr, 90)
                mask = (arr >= q10) & (arr <= q90)
                facteurs[j] = float(np.mean(arr[mask])) if mask.sum() > 0 \
                               else float(np.mean(arr))
            else:
                # Trop peu d'obs → fallback standard
                facteurs[j] = float(np.average(arr, weights=w))

        else:
            # Fallback sécurisé → standard
            logger.warning(
                f"Méthode '{methode}' inconnue — fallback standard"
            )
            facteurs[j] = float(np.average(arr, weights=w))

        # Contrainte : facteur ≥ 1.0
        # Un triangle cumulé ne peut que croître (ou stagner).
        # Un facteur < 1.0 signifie une inversion dans les données.
        if facteurs[j] < 1.0:
            logger.warning(
                f"Facteur j={j} = {facteurs[j]:.4f} < 1.0 "
                f"— forcé à 1.0 (inversion dans le triangle)"
            )
            facteurs[j] = 1.0

    return facteurs, facteurs_ind


# =============================================================================
#  FACTEURS CUMULÉS
# =============================================================================

def calculer_facteurs_cumules(
    facteurs:    np.ndarray,
    tail_factor: float = 1.0,
) -> np.ndarray:
    """
    Calcule les facteurs de développement cumulés de j à ultime.

    F_j = f_j × f_{j+1} × ... × f_{m-2} × tail

    Parameters
    ----------
    facteurs : np.ndarray  shape (m-1,)
        Facteurs individuels f_0, ..., f_{m-2}.
    tail_factor : float
        Facteur tail (développement au-delà de la dernière colonne).
        1.0 si pas de tail.

    Returns
    -------
    f_cum : np.ndarray  shape (m-1,)
        f_cum[j] = facteur cumulé depuis la colonne j jusqu'à ultime.
        f_cum[-1] = tail_factor (colonne finale).
    """
    m     = len(facteurs)
    f_cum = np.ones(m)

    # Partir de la droite (colonne la plus développée)
    f_cum[m - 1] = tail_factor
    for j in range(m - 2, -1, -1):
        f_cum[j] = facteurs[j] * f_cum[j + 1]

    return f_cum


# =============================================================================
#  TAIL FACTOR (RÉGRESSION LOG-LINÉAIRE)
# =============================================================================

def calculer_tail_factor(
    facteurs:             np.ndarray,
    lob_tail_max_alerte:  float = 1.05,
    n_facteurs_queue:     int   = 8,
) -> Dict:
    """
    Estime le tail factor par régression log-linéaire sur les derniers
    facteurs de développement.

    Principe (Mack 1993, Taylor 1986)
    ----------------------------------
    Les facteurs de développement convergent vers 1.0 de façon
    approximativement log-linéaire :

        log(f_j - 1) ≈ a + b × j    avec b < 0 (décroissance)

    On effectue une régression OLS sur les k derniers facteurs
    (k = min(8, n_facteurs)), puis on extrapole :

        tail = Π_{j=m}^{∞} (1 + exp(a + b×j))

    Troncature à convergence : on s'arrête quand f_extrap < 1 + ε
    (ε = 1e-4) ou après 50 itérations max.

    Le tail est clippé à [1.0, 1.20] — un tail > 1.20 est physiquement
    suspect et doit être alerté.

    Parameters
    ----------
    facteurs : np.ndarray
        Vecteur des facteurs f_0, ..., f_{m-2}.
    lob_tail_max_alerte : float
        Seuil d'alerte tail factor depuis lob_config (défaut 1.05).
    n_facteurs_queue : int
        Nombre de facteurs de queue à utiliser pour la régression (défaut 8).

    Returns
    -------
    dict avec tail_factor, methode, statut, message.
    """
    n_f = len(facteurs)

    # Pas assez de facteurs pour régresser
    if n_f < 4:
        return {
            'tail_factor': 1.0,
            'methode':     'aucune (trop peu de facteurs)',
            'statut':      'VERT',
            'message':     "Tail factor = 1.0 — triangle trop court pour régresser.",
        }

    # Utiliser les k derniers facteurs (les plus proches de 1)
    k        = min(n_facteurs_queue, n_f)
    f_queue  = facteurs[n_f - k:]
    x        = np.arange(k, dtype=float)

    # log(f-1) — clip à 1e-8 pour éviter log(0)
    eps = 1e-8
    log_f_m1 = np.log(np.maximum(f_queue - 1.0, eps))

    # Régression OLS : log(f-1) = a + b×x
    try:
        b, a = np.polyfit(x, log_f_m1, 1)

        if b >= 0:
            # Pente positive = facteurs croissants → tail = 1.0
            # (anomalie dans les données, ne pas extrapoler)
            logger.warning(
                f"Tail factor : pente positive b={b:.4f} → tail=1.0 "
                f"(facteurs croissants en queue, vérifier les données)"
            )
            tail = 1.0
        else:
            # Extrapoler au-delà du dernier facteur connu
            tail     = 1.0
            max_iter = 50
            for step in range(max_iter):
                j_extrap   = k + step
                f_extrap   = 1.0 + np.exp(a + b * j_extrap)
                if f_extrap < 1.0 + 1e-4:
                    break
                tail *= f_extrap

    except Exception as e:
        logger.warning(f"Tail factor : régression échouée ({e}) → tail=1.0")
        tail = 1.0

    # Clipper à [1.0, 1.20]
    tail = float(np.clip(tail, 1.0, 1.20))

    # Statut selon seuil LoB
    if tail >= lob_tail_max_alerte:
        statut = 'ROUGE'
    elif tail >= 1.0 + (lob_tail_max_alerte - 1.0) * 0.5:
        statut = 'AMBRE'
    else:
        statut = 'VERT'

    if tail < 1.001:
        msg = (
            f"Tail factor = {tail:.4f} — "
            f"développement considéré complet (tail ≈ 1)."
        )
    else:
        msg = (
            f"Tail factor = {tail:.4f} — "
            f"+{(tail - 1)*100:.2f}% de provisions additionnelles "
            f"au-delà de la dernière colonne."
        )

    return {
        'tail_factor': round(tail, 6),
        'methode':     'régression exponentielle log-linéaire',
        'statut':      statut,
        'message':     msg,
    }


# =============================================================================
#  % DÉVELOPPÉ PAR ANNÉE
# =============================================================================

def calculer_pct_developpe(
    C:     np.ndarray,
    f_cum: np.ndarray,
) -> np.ndarray:
    """
    Pourcentage développé pour chaque année de survenance.

        pct_dev[i] = 1 / F_{k_i}

    où k_i = min(n-i-1, m-1) est la dernière colonne connue de l'année i,
    et F_{k_i} est le facteur cumulé depuis k_i jusqu'à ultime.

    Interprétation : pct_dev[i] = fraction des sinistres déjà payés.
    L'IBNR BF = primes × LR × (1 - pct_dev[i]).

    Parameters
    ----------
    C : np.ndarray  shape (n, m)
    f_cum : np.ndarray  shape (m-1,)

    Returns
    -------
    pct : np.ndarray  shape (n,)
        Valeurs dans [0, 1]. 1.0 = totalement développé.
    """
    n, m = C.shape
    pct  = np.ones(n)

    for i in range(n):
        k = min(n - i - 1, m - 1)   # dernière colonne connue
        if k < len(f_cum) and f_cum[k] > 0:
            pct[i] = 1.0 / f_cum[k]
        else:
            pct[i] = 1.0

    return np.clip(pct, 0.0, 1.0)


# =============================================================================
#  CHAIN LADDER — PROJECTION
# =============================================================================

def chain_ladder(
    C:                  np.ndarray,
    methode:            str   = 'standard',
    annee_base_reserve: int   = 1,
    lob_tail_max_alerte: float = 1.05,
    n_facteurs_queue:   int   = 8,
) -> Dict:
    """
    Chain Ladder complet : facteurs → tail → ultimates → IBNR → réserve.

    Parameters
    ----------
    C : np.ndarray  shape (n, m)
        Triangle cumulé payé. Zéros pour la zone inconnue.
        n : nombre d'années de survenance  (≥ 3)
        m : nombre de périodes de développement  (≥ 3)
        Cas supportés :
          · n = m  (triangle carré, cas standard)
          · n > m  (plus d'années que de colonnes, triangle "court")
          · n < m  (plus de colonnes que d'années, triangle "long", rare)
    methode : str
        Variante CL : 'standard' | 'volume_weighted' | 'mediane' | 'trimmed_mean'
    annee_base_reserve : int
        Index (0-based) de la première année incluse dans la réserve totale.
        Défaut = 1 : exclut i=0 (supposée totalement développée).
        Mettre 0 pour inclure toutes les années.
        Utile pour triangles courts où i=0 n'est pas totalement développée.
    lob_tail_max_alerte : float
        Seuil d'alerte tail (depuis lob_config.tail_factor_max_alerte).
    n_facteurs_queue : int
        Nombre de facteurs utilisés pour la régression tail.

    Returns
    -------
    dict avec :
        facteurs, facteurs_cumules, facteurs_indiv
        tail_factor
        ultimates, ibnr_par_annee, reserve_totale
        pct_developpe, methode, message
    """
    n, m = C.shape

    # ── 1. Facteurs de développement ──────────────────────────────────────────
    facteurs, facteurs_ind = calculer_facteurs(C, methode)

    # ── 2. Tail factor ────────────────────────────────────────────────────────
    tail = calculer_tail_factor(
        facteurs,
        lob_tail_max_alerte=lob_tail_max_alerte,
        n_facteurs_queue=n_facteurs_queue,
    )

    # ── 3. Facteurs cumulés (avec tail) ───────────────────────────────────────
    f_cum = calculer_facteurs_cumules(facteurs, tail['tail_factor'])

    # ── 4. % développé ────────────────────────────────────────────────────────
    pct_dev = calculer_pct_developpe(C, f_cum)

    # ── 5. Ultimates et IBNR ──────────────────────────────────────────────────
    #
    # Pour chaque année i :
    #   k_i = min(n-i-1, m-1)  ← dernière colonne connue
    #   U_i = C[i, k_i] × f_{k_i} × ... × f_{m-2} × tail
    #
    # Implémentation : multiplier C[i, k_i] par les facteurs restants.
    # On utilise les facteurs individuels (pas les cumulés) pour éviter
    # les erreurs d'arrondi sur les très petits/grands triangles.

    ultimates  = np.zeros(n)
    ibnr       = np.zeros(n)
    last_diag  = np.array([
        float(C[i, min(n - i - 1, m - 1)]) for i in range(n)
    ])

    for i in range(n):
        k_i = min(n - i - 1, m - 1)    # dernière colonne connue
        val = float(C[i, k_i])

        # Multiplier par les facteurs restants f_{k_i}, ..., f_{m-2}
        for j in range(k_i, m - 1):
            if j < len(facteurs):
                val *= facteurs[j]

        # Appliquer le tail
        val *= tail['tail_factor']

        ultimates[i] = val
        ibnr[i]      = max(val - last_diag[i], 0.0)

    # ── 6. Réserve totale ─────────────────────────────────────────────────────
    # Par défaut : Σ IBNR_{i=1}^{n-1} (exclure i=0 supposée développée)
    # Paramétrable via annee_base_reserve
    idx_base       = max(0, min(annee_base_reserve, n - 1))
    reserve_totale = float(np.sum(ibnr[idx_base:]))

    # ── 7. Résumé ─────────────────────────────────────────────────────────────
    msg = (
        f"Chain Ladder ({methode}) : "
        f"réserve={reserve_totale:,.0f}€ | "
        f"tail={tail['tail_factor']:.4f} | "
        f"{n}×{m} | base={idx_base}"
    )
    logger.info(msg)

    return {
        # Facteurs
        'facteurs':             [round(float(f), 6) for f in facteurs],
        'facteurs_cumules':     [round(float(f), 6) for f in f_cum],
        'facteurs_indiv':       facteurs_ind,

        # Tail
        'tail_factor':          tail,

        # Résultats
        'ultimates':            [round(float(u), 2) for u in ultimates],
        'ibnr_par_annee':       [round(float(v), 2) for v in ibnr],
        'last_diagonale':       [round(float(d), 2) for d in last_diag],
        'pct_developpe':        [round(float(p), 4) for p in pct_dev],

        # Réserve
        'reserve_totale':       round(reserve_totale, 2),
        'reserve_best_estimate': round(reserve_totale, 2),
        'annee_base_reserve':   idx_base,

        # Métadonnées
        'methode':              f'Chain Ladder ({methode})',
        'n':                    n,
        'm':                    m,
        'message':              msg,
    }
