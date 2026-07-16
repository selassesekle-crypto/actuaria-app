"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ACTUARIA — CIBLE DE SÉVÉRITÉ : LA SOURCE UNIQUE                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Ce que le modèle de coût doit ajuster — et ce qu'il met de côté.            ║
║                                                                              ║
║  POURQUOI CE MODULE EXISTE                                                   ║
║  ─────────────────────────                                                   ║
║  Cette définition existait DEUX fois, et les deux se contredisaient :        ║
║                                                                              ║
║    · pipeline_complet (déclaratif) : cout_ecrete / nb_sinistres, masque      ║
║      (cout_ecrete > 0) & (nb > 0), écrêtement q0.995 → CORRECT.              ║
║    · A3._calibrer_gamma (agent)    : cout_total_sinistres, masque cout > 0,  ║
║      aucun écrêtement → il déclarait 'cout_moyen' et ajustait le TOTAL.      ║
║                                                                              ║
║  Conséquence MESURÉE sur un portefeuille décennale 100k à structure causale  ║
║  connue : le coefficient de `montant` du Gamma d'A3 absorbait AUSSI l'effet  ║
║  fréquence (plus de montant → plus de sinistres → plus de coût TOTAL). Pente ║
║  surestimée, donc prédiction effondrée hors de l'échantillon des sinistrés : ║
║  32 178 € au lieu de 36 797 € (−12,6 %), et Σ primes / Σ charge = 0,85 —     ║
║  A3 SOUS-TARIFIAIT de 15 %. Le chemin déclaratif, lui, tombait à 0,07 % de   ║
║  la vérité du DGP. Une définition dupliquée n'est pas un doublon : c'est une ║
║  divergence en attente.                                                      ║
║                                                                              ║
║  AUTEUR    : ActuarIA                                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

__all__ = ["CibleSeverite", "construire_cible_severite"]


@dataclass(frozen=True)
class CibleSeverite:
    """Le contrat de la cible de sévérité, immuable.

    Attributs
    ─────────
    masque : np.ndarray (bool)
        Contrats retenus pour l'ajustement — ceux où un coût est OBSERVÉ.
    severite : np.ndarray
        cout_ecrete / nb_sinistres sur le masque : le coût PAR SINISTRE.
    seuil_ecretement : float
        Quantile des coûts au-delà duquel un sinistre est dit GRAVE. 0.0 si
        aucun coût observé.
    prime_grave_unitaire : float
        Charge écrêtée, mutualisée PAR UNITÉ D'EXPOSITION. ⚠ À RÉINJECTER dans
        la prime pure : sans elle, on écrête les graves du prix mais pas de la
        réalité — le tarif sous-estime la charge.
    n_retenus, n_graves : int
        Volumétrie, pour les rapports.
    """
    masque:               np.ndarray
    severite:             np.ndarray
    seuil_ecretement:     float
    prime_grave_unitaire: float
    n_retenus:            int
    n_graves:             int


def construire_cible_severite(
    cout_total,
    nb_sinistres,
    exposition,
    *,
    quantile_ecretement: float = 0.995,
    seuil: Optional[float] = None,
) -> CibleSeverite:
    """E[coût PAR SINISTRE], écrêté, là où un coût est OBSERVÉ.

    TROIS décisions, réunies ici parce qu'elles sont indissociables — les
    séparer, c'est exactement ce qui a laissé les deux chemins diverger.

    1. CIBLE — `cout_ecrete / nb_sinistres`, le coût PAR SINISTRE, jamais le
       total. Un contrat à 3 sinistres a un coût total ≈ 3× celui d'un contrat
       à 1 sinistre : ajuster le total, c'est mélanger sévérité et FRÉQUENCE.
       Recombiné en prime pure avec E[N], le nombre est alors compté DEUX FOIS,
       et la pente du facteur de coût absorbe l'effet fréquence.
       Réf. : E[S] = E[N] × E[C | N>0] — la décomposition fréquence-sévérité.

    2. MASQUE — `(cout_ecrete > 0) & (nb_sinistres > 0)` : un coût OBSERVÉ, pas
       seulement un sinistre COMPTÉ. Sur données réelles (freMTPL2), ~9 100
       contrats ont ClaimNb > 0 SANS montant enregistré : leur sévérité vaudrait
       0 et casserait le Gamma (support strictement positif). La FRÉQUENCE, elle,
       garde tous les contrats — le comptage, lui, est observé.

    3. ÉCRÊTEMENT — au quantile `quantile_ecretement`. L'excédent n'est PAS jeté :
       il est mutualisé dans `prime_grave_unitaire`. Sans écrêtement, quelques
       sinistres graves pilotent seuls les relativités du Gamma ; sans
       réinjection, ils disparaissent du tarif. Les deux vont ensemble.

    Paramètres
    ──────────
    seuil : float, optionnel
        None  → le seuil est APPRIS sur ces données (portefeuille d'ajustement).
        float → le seuil FOURNI est appliqué, sans recalcul.
        ⚠ C'est le piège V9, payé cher : on apprend sur le TRAIN et on applique
        au TEST. Recalculer un seuil sur le test y ferait fuiter sa distribution.
    """
    cout = pd.to_numeric(pd.Series(cout_total), errors="coerce").astype(float).fillna(0.0)
    nb   = pd.to_numeric(pd.Series(nb_sinistres), errors="coerce").astype(float).fillna(0.0)
    expo = pd.to_numeric(pd.Series(exposition), errors="coerce").astype(float)

    if seuil is None:
        seuil = (float(cout[cout > 0].quantile(quantile_ecretement))
                 if (cout > 0).any() else 0.0)
    seuil = float(seuil)

    cout_ecrete = cout.clip(upper=seuil) if seuil > 0 else cout
    charge_grave = float((cout - cout_ecrete).sum())
    total_expo = float(expo.sum())
    prime_grave_unitaire = charge_grave / total_expo if total_expo > 0 else 0.0

    masque = ((cout_ecrete > 0) & (nb > 0)).to_numpy()
    severite = (cout_ecrete.to_numpy()[masque] / nb.to_numpy()[masque]).astype(float) \
        if masque.any() else np.empty(0, dtype=float)

    return CibleSeverite(
        masque=masque,
        severite=severite,
        seuil_ecretement=seuil,
        prime_grave_unitaire=prime_grave_unitaire,
        n_retenus=int(masque.sum()),
        n_graves=int((cout > seuil).sum()) if seuil > 0 else 0,
    )
