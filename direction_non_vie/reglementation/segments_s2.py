# =============================================================================
#  ActuarIA — Direction Non-Vie / Réglementation
#  segments_s2.py — LA table officielle des écarts types Solvabilité II
# =============================================================================
#
#  SOURCE, RECOPIÉE MOT À MOT. Règlement délégué (UE) 2015/35, texte consolidé
#  au 02.08.2022 — CELEX 02015R0035-20220802 :
#    · Annexe II   page 389 — engagements NON-VIE, 12 segments
#    · Annexe XIV  page 430 — engagements SANTÉ NON-SLT, 4 segments
#  Les deux tableaux portent le marqueur ▼M6 = Règlement délégué (UE) 2019/981
#  du 8 mars 2019 (JO L 161 du 18.6.2019), rectifié par le rectificatif C3.
#
#  LES ARTICLES QUI S'APPLIQUENT — ET CE N'EST PAS L'ARTICLE 105 :
#    · Art. 115 : SCR(primes et réserve, non-vie) = 3 × σ_nl × V_nl
#    · Art. 116 : les mesures de volume V_prime et V_réserve
#    · Art. 117 : le σ du segment, à partir de σ_prime et σ_réserve
#    · Annexe IV : la matrice de corrélation entre segments (art. 117(1)(c))
#  L'article 105 DU RÈGLEMENT DÉLÉGUÉ porte sur le calcul simplifié du risque
#  de spread des entreprises captives : il n'a rien à voir. La confusion vient
#  de l'article 105 de la DIRECTIVE 2009/138/CE, qui décrit les modules du SCR.
#
#  ┌───────────────────────────────────────────────────────────────────────┐
#  │  POURQUOI CETTE TABLE EST PARTAGÉE, ET NON RECOPIÉE PAR AGENT         │
#  │                                                                       │
#  │  Elle a existé en DEUX exemplaires — un dans A7, un dans A10 — et      │
#  │  ils ont divergé : au moment de les réconcilier, A7 avait 3 valeurs    │
#  │  justes sur 18 et A10 en avait 5 sur 22, sans qu'aucune des deux       │
#  │  copies ne soit une version cohérente d'un texte quelconque. Une       │
#  │  troisième copie divergerait à son tour. C'est un référentiel          │
#  │  réglementaire : il n'appartient à aucun agent.                        │
#  └───────────────────────────────────────────────────────────────────────┘
#
#  QUI SE SERT DE QUELLE COLONNE :
#    · A7 (provisionnement) n'emploie que σ_RÉSERVE. L'art. 117(2) donne
#
#          σ_s = √(σ_p²·V_p² + σ_p·V_p·σ_r·V_r + σ_r²·V_r²) / (V_p + V_r)
#
#      et A7 provisionne des sinistres DÉJÀ SURVENUS : V_prime = 0, donc
#      l'expression se réduit EXACTEMENT à σ_réserve. Ce n'est pas une
#      simplification, c'est la formule standard sur son périmètre.
#    · A10 (Solvabilité II) calcule le module COMPLET primes + réserve : il
#      emploie les deux colonnes et la combinaison ci-dessus.
#
#  ⚠️ PÉRIMÈTRE DE V_RÉSERVE. L'art. 116(6) définit la mesure de volume du
#  risque de réserve comme la meilleure estimation des provisions pour
#  sinistres à payer « après déduction des montants recouvrables au titre des
#  contrats de réassurance et des véhicules de titrisation ».
# =============================================================================

from typing import Dict, NamedTuple, Tuple


class SegmentS2(NamedTuple):
    """Un segment des annexes II ou XIV du Règlement délégué (UE) 2015/35.

    La provenance est portée par la DONNÉE, pas par un commentaire : c'est la
    leçon des lots B10-a et B10-b. Avant eux, les valeurs fausses étaient
    toutes commentées « Annexe II », et certaines citaient un segment qui
    n'existe pas (« CAT naturelles », « Accidents corporels »).
    """
    annexe:          str    # 'II' (non-vie) ou 'XIV' (santé non-SLT)
    numero:          int    # numéro du segment DANS son annexe
    libelle:         str    # libellé officiel, abrégé
    lignes_annexe_i: str    # lignes d'activité qui composent le segment
    sigma_prime:     float  # écart type du risque de primes
    sigma_reserve:   float  # écart type du risque de réserve


#: Clé = (annexe, numéro de segment). Recopie littérale du texte consolidé.
SEGMENTS_S2: Dict[Tuple[str, int], SegmentS2] = {
    # ── Annexe II — engagements NON-VIE (page 389) ───────────────────────────
    ('II',  1): SegmentS2('II',  1, "RC automobile",                     "4 et 16",  0.10,  0.09),
    ('II',  2): SegmentS2('II',  2, "Autre assurance des véhicules",     "5 et 17",  0.08,  0.08),
    ('II',  3): SegmentS2('II',  3, "Maritime, aérienne et transport",   "6 et 18",  0.15,  0.11),
    ('II',  4): SegmentS2('II',  4, "Incendie et autres dommages aux biens", "7 et 19", 0.08, 0.10),
    ('II',  5): SegmentS2('II',  5, "RC générale",                       "8 et 20",  0.14,  0.11),
    ('II',  6): SegmentS2('II',  6, "Crédit et cautionnement",           "9 et 21",  0.19,  0.172),
    ('II',  7): SegmentS2('II',  7, "Protection juridique",              "10 et 22", 0.083, 0.055),
    ('II',  8): SegmentS2('II',  8, "Assistance",                        "11 et 23", 0.064, 0.22),
    ('II',  9): SegmentS2('II',  9, "Pertes pécuniaires diverses",       "12 et 24", 0.13,  0.20),
    ('II', 10): SegmentS2('II', 10, "Réassurance accidents non prop.",   "26",       0.17,  0.20),
    ('II', 11): SegmentS2('II', 11, "Réassurance MAT non prop.",         "27",       0.17,  0.20),
    ('II', 12): SegmentS2('II', 12, "Réassurance dommages non prop.",    "28",       0.17,  0.20),
    # ── Annexe XIV — engagements SANTÉ NON-SLT (page 430) ────────────────────
    ('XIV', 1): SegmentS2('XIV', 1, "Frais médicaux",                    "1 et 13",  0.05,  0.057),
    ('XIV', 2): SegmentS2('XIV', 2, "Protection du revenu",              "2 et 14",  0.085, 0.14),
    ('XIV', 3): SegmentS2('XIV', 3, "Indemnisation des travailleurs",    "3 et 15",  0.096, 0.11),
    ('XIV', 4): SegmentS2('XIV', 4, "Réassurance santé non prop.",       "25",       0.17,  0.17),
}


def libelle_reference(segment: Tuple[str, int]) -> str:
    """Référence à citer dans un livrable : « Annexe XIV, segment 2 — ... ».

    Les rapports écrivaient « Annexe II » EN DUR, ce qui devient faux dès
    qu'une LoB relève de la santé non-SLT. C'est la seule source de cette
    mention.
    """
    seg = SEGMENTS_S2[segment]
    return (f"Annexe {seg.annexe}, segment {seg.numero} — {seg.libelle} "
            f"(Rgt délégué (UE) 2015/35)")


def verifier_rattachements(rattachements: Dict[str, Tuple[str, int]],
                           origine: str) -> None:
    """Lève KeyError si une LoB désigne un segment qui n'existe pas.

    Appelée au CHARGEMENT du module appelant : un mauvais rattachement ne
    peut donc pas atteindre un livrable.
    """
    for cle, segment in rattachements.items():
        if segment not in SEGMENTS_S2:
            raise KeyError(
                f"{origine} : la LoB '{cle}' désigne le segment {segment!r}, "
                f"absent des annexes II et XIV du Règlement délégué (UE) "
                f"2015/35."
            )
