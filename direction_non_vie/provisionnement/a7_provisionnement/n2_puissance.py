# -*- coding: utf-8 -*-
# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n2_puissance.py  —  LA PUISSANCE DISPONIBLE SUR LE TRIANGLE DE L'ACTUAIRE
#
#  Rôle
#  ----
#  Un verdict d'hypothèse dit si l'on a trouvé quelque chose. Il ne dit pas ce
#  qu'on AURAIT pu trouver. « VALIDÉE » confond donc deux affirmations très
#  différentes : « j'ai cherché et il n'y a rien » et « je n'avais aucun moyen
#  de voir quoi que ce soit ». Devant un commissaire aux comptes, ce n'est pas
#  la même phrase.
#
#  Ce module mesure la seconde. Pour chaque hypothèse testable, il répond à :
#  « sur CE portefeuille-ci, quelle proportion des cas ce test aurait-il
#  détectés, pour une violation d'ampleur nommée ? »
#
#  ─────────────────────────────────────────────────────────────────────────────
#  ⚠️ LA RÈGLE QUI COMMANDE TOUT LE MODULE
#
#  UN GÉNÉRATEUR QUI NE RESPECTE PAS LA NULLE DE L'HYPOTHÈSE TESTÉE PRODUIT UN
#  CHIFFRE FAUX — et un chiffre faux publié est pire que pas de chiffre.
#
#  Mesuré, et l'erreur a bien été commise avant d'être corrigée : régénérer
#  depuis l'ajustement ODP donne à CLM-H2 un TÉMOIN de 53 % au lieu de 3 %.
#  La cause est structurelle et non anecdotique — l'ODP pose `E[X_ij] = α_i·β_j`
#  sur les INCRÉMENTS, d'où `E[C_{i,j+1} | C_{ij}] = C_{ij} + α_i·β_{j+1}` :
#  une droite d'ordonnée non nulle, c'est-à-dire exactement ce que CLM-H2
#  rejette. La nulle était violée par le générateur lui-même.
#
#  D'où : CE MODULE NE PORTE QUE LE GÉNÉRATEUR DE MACK, qui est la nulle de
#  CLM-H1, H2 et H3. Les autres familles ont d'autres nulles et exigeront
#  d'autres générateurs — ODP pour BOOT-H3, loss ratio pour BFCC-H5, payé /
#  engagé pour MCL-H2. Chacun devra être validé par son propre témoin AVANT
#  de servir à publier quoi que ce soit.
#
#  ⚠️ CE MODULE N'IMPORTE AUCUNE HYPOTHÈSE. Il reçoit la fonction de test en
#  argument. C'est ce qui évite le cycle d'import avec `n2_hypotheses_clm`,
#  et ce qui rendra les trois autres générateurs greffables sans le toucher.
#
#  Références
#  ----------
#  · Mack, T. (1993) — ASTIN Bulletin 23(2), pp. 213-225 : le modèle régénéré
#    ici, et l'estimateur de σ²_j, extrapolation de la dernière colonne comprise.
# =============================================================================

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np

from .n3.chain_ladder import calculer_facteurs

logger = logging.getLogger('actuaria.a7')

#: Nombre de triangles régénérés par mesure de puissance.
#: ⚠️ QUARANTE, ET C'EST UN ARBITRAGE ASSUMÉ, PAS UNE ÉCONOMIE. L'erreur type
#: vaut ±8 points au pire (p = 50 %), ce qui est SANS IMPORTANCE ici : la
#: publication arrondit à la dizaine, et « environ 70 % » guide un actuaire
#: exactement comme « 71,4 % ». Passer à 100 simulations coûterait deux
#: minutes et demie par exécution pour un chiffre qui s'arrondirait pareil.
N_SIM_PUISSANCE = 40

#: Graine fixe : deux exécutions du même triangle doivent publier le même
#: chiffre. Même valeur et même raison que `SCAN_GRAINE` et
#: `GRAINE_CALIBRATION` — un livrable réglementaire est reproductible.
GRAINE_PUISSANCE = 2023

#: Arrondi de publication. Un actuaire agit sur « environ 70 % » ; la
#: décimale n'ajoute rien et suggérerait une précision que 40 simulations
#: n'ont pas.
PAS_ARRONDI = 10


def ajuster_mack(C: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Facteurs et σ²_j de Mack, estimés SUR LE TRIANGLE DE L'ACTUAIRE.

    C'est ce qui rend le chiffre publié propre à son portefeuille : sa taille,
    ses volumes, sa dispersion réelle. Une puissance mesurée sur des triangles
    de laboratoire ne dirait rien de ce que SON test pouvait voir.

    La dernière colonne n'a qu'une observation : σ²_j y suit la convention de
    Mack (1993, §3) — extrapolation géométrique bornée par les deux
    précédentes, plutôt qu'un zéro qui ferait passer la queue pour certaine.
    """
    C = np.asarray(C, dtype=float)
    n = C.shape[0]
    facteurs, _ = calculer_facteurs(C, 'standard')
    facteurs = np.asarray(facteurs, dtype=float)
    s2: list = []
    for j in range(len(facteurs)):
        termes = [C[i, j] * (C[i, j + 1] / C[i, j] - facteurs[j]) ** 2
                  for i in range(n - j - 1)
                  if C[i, j] > 0 and C[i, j + 1] > 0]
        if len(termes) > 1:
            s2.append(sum(termes) / (len(termes) - 1))
        elif len(s2) > 1:
            s2.append(min(s2[-1] ** 2 / s2[-2], s2[-1], s2[-2]))
        elif s2:
            s2.append(s2[-1])
        else:
            s2.append(0.0)
    return facteurs, np.asarray(s2, dtype=float)


def regenerer_mack(
    C0:              np.ndarray,
    facteurs:        np.ndarray,
    s2:              np.ndarray,
    rng:             np.random.Generator,
    choc_diagonale:  Optional[int] = None,
    ampleur:         float = 1.0,
    intercept:       float = 0.0,
    expo_var:        float = 1.0,
) -> np.ndarray:
    """Un triangle tiré du modèle de MACK ajusté au triangle réel.

        C[i,j+1] = f_j·C[i,j] + intercept + σ_j·C[i,j]^(expo_var/2)·Z

    Sans violation, ce tirage satisfait EXACTEMENT les trois hypothèses :
    espérance proportionnelle (H2), variance en C (H3), années indépendantes
    (H1). C'est ce qui autorise à appeler « puissance » ce qu'on mesure — le
    témoin doit avoisiner le seuil nominal, et il est vérifié par le filet.

    Chaque paramètre viole UNE hypothèse et une seule :
      · `choc_diagonale` + `ampleur` — les règlements d'UNE année calendaire
        sont majorés : c'est l'effet calendaire de CLM-H1 ;
      · `intercept` — la relation ne passe plus par l'origine : CLM-H2 ;
      · `expo_var` — la dispersion croît plus vite que le volume : CLM-H3.
    """
    C0 = np.asarray(C0, dtype=float)
    n = C0.shape[0]
    C = np.zeros((n, n))
    C[:, 0] = C0[:, 0]
    for i in range(n):
        for j in range(1, n - i):
            c = C[i, j - 1]
            ecart = np.sqrt(max(float(s2[j - 1]), 0.0)) * c ** (expo_var / 2.0)
            C[i, j] = max(facteurs[j - 1] * c + intercept +
                          ecart * rng.standard_normal(), c * 1.0001)
    if choc_diagonale is not None and ampleur != 1.0:
        # Un effet calendaire majore les RÈGLEMENTS DE L'ANNÉE, donc les
        # incréments d'une diagonale — pas tout ce qui suit.
        increments = np.diff(np.column_stack([np.zeros(n), C]), axis=1)
        for i in range(n):
            j = choc_diagonale - i
            if 0 <= j < n - i:
                increments[i, j] *= ampleur
        C = np.cumsum(increments, axis=1)
    for i in range(n):
        for j in range(n - i, n):
            C[i, j] = 0.0
    return C


def taux_de_detection(
    C0:      np.ndarray,
    test:    Callable[[np.ndarray], Any],
    n_sim:   int = N_SIM_PUISSANCE,
    graine:  int = GRAINE_PUISSANCE,
    **violation: Any,
) -> Optional[float]:
    """Proportion de triangles régénérés — et violés — que `test` signale.

    Sans `violation`, c'est le TÉMOIN : il doit avoisiner le seuil nominal du
    test, et c'est la seule preuve que le générateur respecte bien sa nulle.
    """
    try:
        facteurs, s2 = ajuster_mack(C0)
    except Exception:                                      # pragma: no cover
        return None
    rng = np.random.default_rng(graine)
    detectes = evalues = 0
    for _ in range(n_sim):
        try:
            r = test(regenerer_mack(C0, facteurs, s2, rng, **violation))
            statut = str(getattr(r, 'statut', r))
        except Exception:                                  # pragma: no cover
            continue
        evalues += 1
        if statut not in ('VALIDÉE', 'NON TESTABLE'):
            detectes += 1
    return (100.0 * detectes / evalues) if evalues else None


def arrondir(pourcentage: float) -> int:
    """À la dizaine — 40 simulations ne portent pas plus de précision."""
    return int(PAS_ARRONDI * round(pourcentage / PAS_ARRONDI))


def formuler(pourcentage: float, effet: str, levier: str = '') -> str:
    """La phrase publiée à côté du verdict.

    ⚠️ REGISTRE AFFIRMATIF, ET C'EST UNE EXIGENCE MÉTIER. Publier une
    puissance est une FORCE : cela énonce précisément ce que le test pouvait
    voir, là où le marché se contente d'un « validée » muet. Une puissance
    faible n'est pas un aveu — c'est une information que personne d'autre ne
    donne, et elle protège l'actuaire qui signe. Aucune formulation ne doit
    laisser entendre que l'outil doute de lui-même.
    """
    p = arrondir(pourcentage)
    if p >= 80:
        return (f"Ce test disposait de la puissance nécessaire : sur ce "
                f"portefeuille, il détecterait {effet} dans {p} % des cas. "
                f"Le verdict est opposable.")
    if p >= 40:
        return (f"Sur ce portefeuille, ce test détecterait {effet} dans "
                f"{p} % des cas.")
    complement = f" — {levier}" if levier else ""
    return (f"Sur ce portefeuille, ce test détecterait {effet} dans {p} % "
            f"des cas{complement}. Le verdict énonce donc une absence de "
            f"contradiction, mesurée, et non une vérification.")


def sans_objet(motif: str) -> Dict[str, Any]:
    """Pour les hypothèses qui ne sont pas des tests statistiques.

    Sept des dix-neuf sont des contrôles de plage ou de comptage : elles
    n'ont pas de puissance, et inventer un chiffre serait pire que de le
    dire. On le dit.
    """
    return {'mesurable': False, 'motif': motif,
            'phrase': f"Cette vérification n'est pas un test statistique : "
                      f"{motif}. La notion de puissance n'y a pas de sens."}
