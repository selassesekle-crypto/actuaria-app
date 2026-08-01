# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  config/lob_config.py
#  Configuration par Ligne d'Activité (LoB) Solvabilité II
# =============================================================================
#
#  Référence réglementaire :
#    - EIOPA Guidelines on the valuation of technical provisions (EIOPA-BoS-14/166)
#    - Annexe I du Règlement Délégué 2015/35 : classification des LoB Non-Vie
#    - FFSA/FFA : données marché et benchmarks LR par branche
#
#  Chaque LoB définit :
#    · seuils H1/H2 adaptés au comportement réel de la branche
#    · longueur de queue attendue (en années)
#    · méthodes actuarielles prioritaires
#    · alertes spécifiques à la branche
#    · le SEGMENT officiel Solvabilité II dont elle relève (cf. SEGMENTS_S2)
#    · LR marché de référence (source FFA/FFSA)
#
# =============================================================================

from typing import Any, Dict

# ─────────────────────────────────────────────────────────────────────────────
#  LES SEGMENTS OFFICIELS — TABLE PARTAGÉE, PAS UNE COPIE
#
#  La table des écarts types réglementaires vit désormais dans
#  `direction_non_vie/reglementation/segments_s2.py`, avec sa source et ses
#  articles. Elle y a été DÉPLACÉE au lot B10-b, parce qu'A10 en détenait sa
#  propre copie et que les deux avaient divergé : A7 avait 3 valeurs justes
#  sur 18, A10 en avait 5 sur 22. Une copie par agent est le mécanisme même
#  de la dérive ; un référentiel réglementaire n'appartient à aucun agent.
#
#  POURQUOI A7 N'UTILISE QUE σ_RÉSERVE. L'article 117(2) donne
#
#      σ_s = √(σ_p²·V_p² + σ_p·V_p·σ_r·V_r + σ_r²·V_r²) / (V_p + V_r)
#
#  A7 provisionne des sinistres DÉJÀ SURVENUS : il n'y a pas de prime future,
#  donc V_prime = 0 et l'expression se réduit EXACTEMENT à σ_réserve. A7 n'a
#  donc besoin que d'UN σ par segment, et c'est bien celui de la réserve — ce
#  n'est pas une simplification, c'est la formule standard sur son périmètre.
#  A10, qui calcule le module complet primes + réserve, emploie les deux.
#
#  ⚠️ PÉRIMÈTRE DE V_RÉSERVE. L'article 116(6) définit la mesure de volume du
#  risque de réserve comme la meilleure estimation des provisions pour
#  sinistres à payer « après déduction des montants recouvrables au titre des
#  contrats de réassurance et des véhicules de titrisation ». Le Best Estimate
#  d'A7 est BRUT de réassurance (étiquetage posé au commit 244f3e6) : le SCR
#  publié est donc un MAJORANT sur cet axe. La cession n'est pas dans le
#  périmètre d'A7 — A10 opère en aval.
# ─────────────────────────────────────────────────────────────────────────────

from ....reglementation.segments_s2 import (  # noqa: F401  (ré-export)
    SegmentS2, SEGMENTS_S2, libelle_reference, verifier_rattachements)

# ─────────────────────────────────────────────────────────────────────────────
#  MATRICE DE CORRÉLATION EIOPA Non-Vie 12×12
#  Source : Annexe IV, Règlement Délégué (UE) 2015/35
#  Utilisée pour l'agrégation SCR_NL = sqrt(Σ_ij ρ_ij × SCR_i × SCR_j)
# ─────────────────────────────────────────────────────────────────────────────
# Ordre des LoB : 1=frais_med, 2=prot_rev, 3=ind_trav, 4=rc_auto,
#                 5=auto_dom, 6=mat, 7=incendie, 8=rc_gen,
#                 9=credit, 10=prot_jur, 11=assist, 12=pertes
CORRELATION_EIOPA = [
    # 1     2     3     4     5     6     7     8     9    10    11    12
    [1.00, 0.50, 0.50, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],  # 1
    [0.50, 1.00, 0.50, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],  # 2
    [0.50, 0.50, 1.00, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],  # 3
    [0.25, 0.25, 0.25, 1.00, 0.50, 0.25, 0.25, 0.50, 0.25, 0.25, 0.25, 0.25],  # 4
    [0.25, 0.25, 0.25, 0.50, 1.00, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],  # 5
    [0.25, 0.25, 0.25, 0.25, 0.25, 1.00, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],  # 6
    [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 1.00, 0.25, 0.25, 0.25, 0.25, 0.25],  # 7
    [0.25, 0.25, 0.25, 0.50, 0.25, 0.25, 0.25, 1.00, 0.50, 0.25, 0.25, 0.25],  # 8
    [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.50, 1.00, 0.25, 0.25, 0.25],  # 9
    [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 1.00, 0.25, 0.25],  # 10
    [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 1.00, 0.25],  # 11
    [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 1.00],  # 12
]

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION PAR BRANCHE
#  Chaque entrée est identifiée par une clé string (lob_id)
#  passée dans AgentA7Provisionnement.run(lob='rc_auto_corporels')
# ─────────────────────────────────────────────────────────────────────────────
LOB_CONFIG: Dict[str, Dict[str, Any]] = {

    # ── RC Automobile — matériels (queue courte) ──────────────────────────────
    "rc_auto_materiel": {
        "label":            "RC Automobile — Dommages Matériels",
        # « RC Automobile » = responsabilité civile : le dommage matériel visé
        # est celui causé AU TIERS, donc ligne d'activité 4, segment II-1 —
        # et non le segment II-2, qui couvre les dommages au véhicule assuré.
        "segment_s2":       ('II', 1),

        # Longueur de développement attendue
        "queue_attendue_ans": 5,

        # Seuils H2 adaptés : Auto matériel = portefeuille stable, peu de variance
        "h2_seuil_cv":      0.12,   # CV max acceptable des facteurs
        "h2_seuil_derive":  0.15,   # dérive temporelle max acceptable

        # H1 : seuil corrélation Spearman pour alerte
        "h1_seuil_corr":    0.50,

        # Méthodes prioritaires (ordre de confiance décroissant)
        "methodes_prioritaires": ["chain_ladder", "mack_1993", "bootstrap_odp"],

        # Munich CL : non pertinent sans triangle engagé fiable
        "munich_cl_disponible": False,

        # LR marché de référence (source FFA Non-Vie 2024)
        "lr_marche_reference":  0.72,
        "lr_marche_source":     "FFA Non-Vie 2024 — RC Auto matériels",

        # Alertes spécifiques à la branche
        "alertes_specifiques": [
            "Vérifier l'impact de l'inflation pièces détachées post-2021 sur les facteurs récents.",
            "Contrôler la stabilité des facteurs si réforme du barème IDA en cours.",
        ],

        # Tail factor : en général proche de 1.00 pour auto matériel
        "tail_factor_max_alerte": 1.02,

        # Tail factor — Guide IA 2023 : RC Auto Matériel = risque court (< 5 ans)
        "risque_long":              False,  # risque court → tail_factor forcé à 1.0
        "tail_seuil_stabilisation": 1.01,   # inerte tant que risque_long=False
    },

    # ── RC Automobile — corporels (queue très longue) ─────────────────────────
    "rc_auto_corporels": {
        "label":            "RC Automobile — Corporels",
        "segment_s2":       ('II', 1),

        "queue_attendue_ans": 20,

        # Queue longue → plus de tolérance sur le CV, mais surveiller la dérive
        "h2_seuil_cv":      0.20,
        "h2_seuil_derive":  0.25,
        "h1_seuil_corr":    0.50,

        "methodes_prioritaires": [
            "mack_1993", "bornhuetter_ferguson", "bootstrap_odp", "chain_ladder"
        ],
        "munich_cl_disponible": True,

        "lr_marche_reference":  0.85,
        "lr_marche_source":     "FFA Non-Vie 2024 — RC Auto corporels",

        "alertes_specifiques": [
            "ATTENTION : branche à queue très longue (15–25 ans). "
            "Vérifier le tail factor — un tail > 1.05 est anormal.",
            "Surveiller l'évolution de la jurisprudence Dintilhac "
            "(révision du barème de capitalisation).",
            "Contrôler l'impact de l'inflation médicale sur les rentes corporelles.",
            "Les recours FGAO doivent être isolés du triangle principal.",
        ],

        "tail_factor_max_alerte": 1.05,

        # Tail factor — Guide IA 2023 (pratique professionnelle française)
        "risque_long":              True,  # RC Auto Corporels = risque long (15-25 ans)
        "tail_seuil_stabilisation": 1.1,
    },

    # ── MRH — Multirisque Habitation (queue courte) ───────────────────────────
    "mrh": {
        "label":            "Multirisque Habitation (MRH)",
        "segment_s2":       ('II', 4),

        "queue_attendue_ans": 4,

        # MRH = portefeuille très stable → seuils stricts
        "h2_seuil_cv":      0.12,
        "h2_seuil_derive":  0.12,
        "h1_seuil_corr":    0.45,

        "methodes_prioritaires": ["chain_ladder", "bootstrap_odp", "mack_1993"],
        "munich_cl_disponible":  False,

        "lr_marche_reference":  0.68,
        "lr_marche_source":     "FFA Non-Vie 2024 — MRH",

        "alertes_specifiques": [
            "Isoler impérativement les sinistres CAT NAT (tempêtes, inondations, grêle) "
            "avant le calcul Chain Ladder — ils faussent les facteurs.",
            "Contrôler l'impact de l'inflation matériaux BTP post-2021 "
            "sur le coût moyen des sinistres incendie.",
            "Vérifier la saisonnalité des sinistres gel/dégât des eaux "
            "(diagonale Q4 systématiquement plus élevée).",
        ],

        "tail_factor_max_alerte": 1.01,

        # Tail factor — Guide IA 2023 : MRH = risque court (< 4 ans)
        "risque_long":              False,
        "tail_seuil_stabilisation": 1.01,
    },

    # ── RC Générale (queue moyenne) ───────────────────────────────────────────
    "rc_generale": {
        "label":            "Responsabilité Civile Générale",
        "segment_s2":       ('II', 5),

        "queue_attendue_ans": 12,

        "h2_seuil_cv":      0.18,
        "h2_seuil_derive":  0.20,
        "h1_seuil_corr":    0.50,

        "methodes_prioritaires": [
            "bornhuetter_ferguson", "cape_cod", "mack_1993", "bootstrap_odp"
        ],
        "munich_cl_disponible": True,

        "lr_marche_reference":  0.78,
        "lr_marche_source":     "FFA Non-Vie 2024 — RC Générale",

        "alertes_specifiques": [
            "Attention aux sinistres sériels (produits défectueux, contamination) "
            "— les isoler avant calcul CL.",
            "Surveiller les sinistres émergents à déclaration tardive "
            "(délai > 3 ans entre fait générateur et déclaration).",
            "Contrôler la stabilité du ratio S/P vs N-1 : "
            "une hausse > 5 pts doit être documentée.",
        ],

        "tail_factor_max_alerte": 1.04,

        # Tail factor — Guide IA 2023 (pratique professionnelle française)
        "risque_long":              True,  # RC Générale = risque long, seuil 1.05
        "tail_seuil_stabilisation": 1.05,
    },

    # ── RC Médicale (queue très longue) ───────────────────────────────────────
    "rc_medicale": {
        "label":            "Responsabilité Civile Médicale",
        # La « RC professionnelle » n'est pas un segment : l'annexe II range la
        # responsabilité civile médicale dans la RC générale (ligne 8).
        "segment_s2":       ('II', 5),

        "queue_attendue_ans": 25,

        # Très longue queue → tolérance haute sur CV
        "h2_seuil_cv":      0.25,
        "h2_seuil_derive":  0.30,
        "h1_seuil_corr":    0.55,

        "methodes_prioritaires": [
            "bornhuetter_ferguson", "mack_1993", "cape_cod", "bootstrap_odp"
        ],
        "munich_cl_disponible": True,

        "lr_marche_reference":  0.92,
        "lr_marche_source":     "MACSF/Sham — RC Médicale 2024",

        "alertes_specifiques": [
            "BRANCHE À QUEUE TRÈS LONGUE (20–30 ans). "
            "Un triangle < 15 ans est insuffisant pour calibrer les facteurs de queue.",
            "Surveiller l'évolution de la loi Kouchner et les délais CRCI/CCI "
            "(impact sur le rythme de déclaration).",
            "L'inflation médicale différenciée (honoraires vs hospit vs équipement) "
            "doit être intégrée dans l'a priori BF.",
            "Vérifier la cohérence avec les benchmarks ONIAM.",
            "Discount obligatoire sur les rentes long terme (Art. 77 S2).",
        ],

        "tail_factor_max_alerte": 1.10,

        # Tail factor — Guide IA 2023 (pratique professionnelle française)
        "risque_long":              True,  # RC Médicale = risque très long (20-30 ans)
        "tail_seuil_stabilisation": 1.1,
    },

    # ── Construction — RC Décennale / DO (queue longue) ──────────────────────
    "construction": {
        "label":            "Construction — RC Décennale / Dommages-Ouvrage",
        # La décennale est de la responsabilité civile : segment II-5, comme la
        # RC médicale. Il n'existe pas de segment « construction ».
        "segment_s2":       ('II', 5),

        "queue_attendue_ans": 15,

        # Triangles souvent creux (déclaration différée jusqu'à 10 ans)
        "h2_seuil_cv":      0.25,
        "h2_seuil_derive":  0.25,
        "h1_seuil_corr":    0.55,

        "methodes_prioritaires": [
            "bornhuetter_ferguson", "cape_cod", "mack_1993"
        ],
        "munich_cl_disponible": False,

        "lr_marche_reference":  0.88,
        "lr_marche_source":     "FFA Non-Vie 2024 — Construction",

        "alertes_specifiques": [
            "ATTENTION : garantie décennale = déclaration différée jusqu'à 10 ans. "
            "La zone connue du triangle sera structurellement creuse.",
            "BF fortement recommandé sur les années récentes (< 5 ans de développement).",
            "Surveiller les insolvabilités constructeurs "
            "(impact sur les recours en garantie).",
            "Isoler les sinistres sériels (défaut de conception vs défaut d'exécution).",
        ],

        "tail_factor_max_alerte": 1.06,

        # Tail factor — Guide IA 2023 : applicable uniquement si risque long
        # ET coefficients non stabilisés (dernier LDF > tail_seuil_stabilisation)
        "risque_long":              True,  # Construction = risque long (15 ans)
                "tail_seuil_stabilisation": 1.1,  # LDF < 1.10 = développement faible = stabilisé
    },

    # ── Marine / Aviation / Transport ─────────────────────────────────────────
    "marine_aviation_transport": {
        "label":            "Marine, Aviation et Transport",
        # UN SEUL segment officiel couvre les trois : II-3 « maritime, aérienne
        # et transport ». Le commentaire retiré ici inventait trois
        # sous-segments (Transport 0,12 / Maritime 0,12 / Aviation 0,14) dont
        # aucun ne figure à l'annexe II.
        "segment_s2":       ('II', 3),

        "queue_attendue_ans": 8,

        "h2_seuil_cv":      0.22,
        "h2_seuil_derive":  0.22,
        "h1_seuil_corr":    0.50,

        "methodes_prioritaires": [
            "bornhuetter_ferguson", "cape_cod", "mack_1993", "bootstrap_odp"
        ],
        "munich_cl_disponible": False,

        "lr_marche_reference":  0.82,
        "lr_marche_source":     "FFA Non-Vie 2024 — Marine/Transport",

        "alertes_specifiques": [
            "Portefeuille à fort risque de concentration : "
            "1 sinistre peut représenter 30–40% du portefeuille.",
            "Isoler les gros sinistres (Large Loss Threshold) avant calcul CL.",
            "Vérifier la séparation brut/net de réassurance.",
            "Surveiller l'exposition aux CAT maritimes et aux événements géopolitiques.",
        ],

        "tail_factor_max_alerte": 1.03,

        # Tail factor — Guide IA 2023 (pratique professionnelle française)
        "risque_long":              True,  # Transport = risque long, seuil 1.05
        "tail_seuil_stabilisation": 1.05,
    },

    # ── Accidents Corporels (LoB 1 S2 — GAV, accident scolaire, individuelle) ──
    "accidents_corporels": {
        "label":            "Accidents Corporels — queue COURTE (6 ans)",
        # ⚠️ MÊME LoB SOLVABILITÉ II QUE `dommage_corporel_individuel`, MÊME σ :
        # ce qui distingue les deux n'est pas le segment réglementaire mais le
        # RÉGIME DE QUEUE. Ici `risque_long = False`. Se tromper entre les deux
        # change le facteur de queue, donc l'ultime — et rien ne le signalait,
        # les deux libellés étant quasi identiques. Cf. `distinction`.
        "distinction":      "queue courte, risque_long=False — sinistres se "
                            "dénouant rapidement (GAV, accident scolaire). Pour "
                            "un dénouement long avec rentes potentielles, "
                            "utiliser 'dommage_corporel_individuel'.",
        # CLÉ FANTÔME TRANCHÉE (lot B10-a). Le σ de 0,085 était commenté
        # « Annexe II — Accidents corporels » : ce segment N'EXISTE PAS. Les
        # garanties d'atteinte corporelle relèvent de la santé non-SLT, et le
        # segment retenu est XIV-2 « protection du revenu » plutôt que XIV-1
        # « frais médicaux », par cohérence avec `dommage_corporel_individuel`
        # qui partage ce segment et sert des rentes.
        "segment_s2":       ('XIV', 2),

        "queue_attendue_ans": 6,

        "h2_seuil_cv":      0.15,
        "h2_seuil_derive":  0.15,
        "h1_seuil_corr":    0.55,

        "methodes_prioritaires": [
            "chain_ladder", "mack_1993", "bornhuetter_ferguson", "bootstrap_odp"
        ],
        "munich_cl_disponible": False,

        "lr_marche_reference":  0.70,
        "lr_marche_source":     "Marché français — GAV / Accident scolaire (estimation)",

        "alertes_specifiques": [
            "Portefeuille court — vérifier suffisance du triangle (min 5 ans).",
            "Distinguer GAV individuelle et collective (sinistralité différente).",
        ],

        "tail_factor_max_alerte": 1.03,
        "risque_long":              False,
        "tail_seuil_stabilisation": 1.02,
    },

    # ── Transport (LoB 6 S2 — sous-catégorie marine_aviation_transport) ────────
    "transport": {
        "label":            "Transport",
        "segment_s2":       ('II', 3),

        "queue_attendue_ans": 8,

        "h2_seuil_cv":      0.22,
        "h2_seuil_derive":  0.22,
        "h1_seuil_corr":    0.50,

        "methodes_prioritaires": [
            "bornhuetter_ferguson", "cape_cod", "mack_1993", "bootstrap_odp"
        ],
        "munich_cl_disponible": False,

        "lr_marche_reference":  0.82,
        "lr_marche_source":     "FFA Non-Vie 2024 — Transport",

        "alertes_specifiques": [
            "Portefeuille à fort risque de concentration — isoler les gros sinistres.",
            "Vérifier la séparation brut/net de réassurance.",
            "Surveiller l'exposition aux événements géopolitiques et climatiques.",
        ],

        "tail_factor_max_alerte": 1.05,
        "risque_long":              True,
        "tail_seuil_stabilisation": 1.05,
    },

    # ── Générique (fallback si lob non spécifié) ──────────────────────────────
    "generique": {
        "label":            "Branche Non-Vie Générique",
        "segment_s2":       ('II', 5),

        "queue_attendue_ans": 10,

        # Seuils standards marché
        "h2_seuil_cv":      0.15,
        "h2_seuil_derive":  0.20,
        "h1_seuil_corr":    0.50,

        "methodes_prioritaires": [
            "chain_ladder", "mack_1993", "bornhuetter_ferguson",
            "cape_cod", "bootstrap_odp"
        ],
        "munich_cl_disponible": False,

        "lr_marche_reference":  None,
        "lr_marche_source":     "Aucun benchmark disponible — à calibrer sur données internes",

        "alertes_specifiques": [
            "Branche non identifiée. Les seuils H2 génériques (CV=15%, dérive=20%) "
            "sont appliqués. Préciser le paramètre 'lob' pour une analyse adaptée.",
        ],

        "tail_factor_max_alerte": 1.05,

        # Tail factor — Guide IA 2023 : générique = branche inconnue, traitée
        # comme risque long par prudence. tail_seuil = 1.02 retenu (pas 1.10).
        "risque_long":              True,   # prudence maximale
        "tail_seuil_stabilisation": 1.02,   # LDF < 1.02 = développement quasi nul
    },
    # =========================================================================
    #  5.b — INCENDIE & DOMMAGES AUX BIENS (hors MRH)
    #  Guide IA 2023 p.42 — Risque court, liquidation 3-5 ans
    # =========================================================================
    "incendie_dommages": {
        "label":            "Incendie & Dommages aux Biens",
        "segment_s2":       ('II', 4),
        "queue_attendue_ans": 5,
        "h2_seuil_cv":      0.15,
        "h2_seuil_derive":  0.20,
        "h1_seuil_corr":    0.50,
        "methodes_prioritaires": ["chain_ladder", "bornhuetter_ferguson", "bootstrap_odp"],
        "munich_cl_disponible": False,
        "lr_marche_reference":  0.68,
        "lr_marche_source":     "Marché français FFSA — Dommages aux biens",
        "risque_long":              False,
        "tail_seuil_stabilisation": 1.01,
        "tail_factor_max_alerte":   1.02,
        "alertes_specifiques": [
            "Séparer Cat Nat des autres garanties.",
            "Retraiter l'inflation via indice FFB avant projection.",
            "Distinguer attritionnels et graves si volume suffisant.",
        ],
    },

    # =========================================================================
    #  5.c — PROTECTION JURIDIQUE
    #  Guide IA 2023 p.43-44 — Risque court, liquidation 5-8 ans
    # =========================================================================
    "protection_juridique": {
        "label":            "Protection Juridique",
        "segment_s2":       ('II', 7),
        "queue_attendue_ans": 8,
        "h2_seuil_cv":      0.15,
        "h2_seuil_derive":  0.20,
        "h1_seuil_corr":    0.50,
        "methodes_prioritaires": ["chain_ladder", "bornhuetter_ferguson", "bootstrap_odp"],
        "munich_cl_disponible": False,
        "lr_marche_reference":  0.72,
        "lr_marche_source":     "Marché français — Protection Juridique",
        "risque_long":              False,
        "tail_seuil_stabilisation": 1.01,
        "tail_factor_max_alerte":   1.02,
        "alertes_specifiques": [
            "Date déclaration = date survenance (Guide IA 2023 p.43).",
            "Peu de sinistres tardifs — ne pas confondre avec RC.",
            "Séparer PJ accessoire et PJ directe si données disponibles.",
        ],
    },

    # =========================================================================
    #  5.g — CATASTROPHES NATURELLES (Cat-Nat)
    #  Guide IA 2023 p.50-51 — Risque court mais très volatil
    # =========================================================================
    "catastrophes_naturelles": {
        "label":            "Catastrophes Naturelles (Cat-Nat)",
        # ⚠️ CLÉ FANTÔME TRANCHÉE (lot B10-a) — ET C'EST LA PLUS GROSSE BAISSE
        # DU LOT. Le σ valait 0,25, commenté « Annexe II — CAT naturelles » :
        # ce segment N'EXISTE PAS, et le 0,25 n'avait aucune source. Le risque
        # de RÉSERVE d'un portefeuille cat-nat, c'est-à-dire l'incertitude sur
        # les sinistres DÉJÀ SURVENUS, est celui du segment II-4 comme pour
        # tout dommage aux biens : 10 %. Le SCR de cette LoB baisse de 60 %.
        #
        # CE QUE CE σ NE COUVRE PAS, ET QUI EXPLIQUE POURQUOI IL PARAÎT FAIBLE :
        # le risque de catastrophe proprement dit — la survenance d'événements
        # FUTURS — est un module distinct du SCR (art. 119 et suivants, annexes
        # V, VI et X). A7 provisionne, il ne le calcule pas et n'a pas à le
        # calculer. Le SCR affiché par A7 sur cette branche n'est donc PAS la
        # charge en capital totale d'un portefeuille cat-nat : il lui manque le
        # module catastrophe, qui relève d'A10.
        "segment_s2":       ('II', 4),
        "queue_attendue_ans": 7,
        "h2_seuil_cv":      0.25,
        "h2_seuil_derive":  0.35,
        "h1_seuil_corr":    0.40,
        "methodes_prioritaires": ["bornhuetter_ferguson", "cape_cod", "chain_ladder"],
        "munich_cl_disponible": False,
        "lr_marche_reference":  None,
        "lr_marche_source":     "Référence CCR/MRN par événement",
        "risque_long":              False,
        "tail_seuil_stabilisation": 1.02,
        "tail_factor_max_alerte":   1.05,
        "alertes_specifiques": [
            "Effets calendaires forts — séparer les périls (tempête, sécheresse, inondation, séisme).",
            "Utiliser les données CCR/MRN pour calibrer les charges ultimes.",
            "Sécheresse : cadence très différente des autres périls.",
            "Provisions d'égalisation obligatoires en norme S1 (Art. R331-33).",
        ],
    },

    # =========================================================================
    #  5.h — CRÉDIT / CAUTION
    #  Guide IA 2023 p.52-53 — Risque moyen, corrélation économique forte
    # =========================================================================
    "credit_caution": {
        "label":            "Crédit / Caution",
        "segment_s2":       ('II', 6),
        "queue_attendue_ans": 12,
        "h2_seuil_cv":      0.20,
        "h2_seuil_derive":  0.30,
        "h1_seuil_corr":    0.45,
        "methodes_prioritaires": ["bornhuetter_ferguson", "cape_cod", "chain_ladder"],
        "munich_cl_disponible": False,
        "lr_marche_reference":  None,
        "lr_marche_source":     "À calibrer par secteur — corrélation cycle économique",
        "risque_long":              True,
        "tail_seuil_stabilisation": 1.05,
        "tail_factor_max_alerte":   1.04,
        "alertes_specifiques": [
            "Traiter par année de souscription (Guide IA 2023 p.52).",
            "Forte corrélation avec le cycle économique.",
            "Provisions complémentaires : provision d'égalisation, provision pour menace.",
            "Distinguer assurance-crédit et caution.",
        ],
    },

    # =========================================================================
    #  5.j — DOMMAGE CORPOREL INDIVIDUEL
    #  Guide IA 2023 p.55-56 — Risque moyen, rentes potentielles
    # =========================================================================
    "dommage_corporel_individuel": {
        "label":            "Dommage Corporel Individuel — queue LONGUE (7 ans)",
        # ⚠️ MÊME LoB SOLVABILITÉ II QUE `accidents_corporels`, MÊME σ — cf. le
        # commentaire là-bas. Ici `risque_long = True`, ce qui change le facteur
        # de queue et donc l'ultime.
        "distinction":      "queue longue, risque_long=True — dénouement lent, "
                            "rentes potentielles, inflation judiciaire. Pour un "
                            "dénouement rapide, utiliser 'accidents_corporels'.",
        "segment_s2":       ('XIV', 2),
        "queue_attendue_ans": 7,
        "h2_seuil_cv":      0.15,
        "h2_seuil_derive":  0.20,
        "h1_seuil_corr":    0.50,
        "methodes_prioritaires": ["bornhuetter_ferguson", "chain_ladder", "mack_1993", "bootstrap_odp"],
        "munich_cl_disponible": False,
        "lr_marche_reference":  0.75,
        "lr_marche_source":     "Marché français — GAV / Accident scolaire (estimation)",
        "risque_long":              True,
        "tail_seuil_stabilisation": 1.05,
        "tail_factor_max_alerte":   1.04,
        "alertes_specifiques": [
            "Distinguer sinistres transigés en capital et rentes potentielles.",
            "Provisions Mathématiques de rente pour les rentes constituées.",
            "Retraiter l'inflation judiciaire (BCRIV, Gazette du palais).",
        ],
    },

}

# ─────────────────────────────────────────────────────────────────────────────
#  LE σ EST DÉRIVÉ DE LA TABLE, JAMAIS SAISI
#
#  C'est ce qui rend impossible la dérive qui a rendu ce lot nécessaire. Avant
#  lui, chaque LoB portait DEUX champs qui disaient la même chose — `lob_eiopa`
#  (un texte) et `sigma_eiopa` (un nombre) — et ils se contredisaient sur trois
#  LoB sur quinze : `catastrophes_naturelles` déclarait relever d'incendie tout
#  en prenant un σ de 0,25 sans source, `rc_medicale` et `construction`
#  déclaraient la RC générale tout en prenant 0,14 au lieu de son σ. Un seul
#  champ subsiste désormais, `segment_s2`, et le nombre en découle.
# ─────────────────────────────────────────────────────────────────────────────

def _appliquer_table_officielle() -> None:
    """Injecte `sigma_eiopa` dans chaque LoB à partir de son segment officiel.

    Lève KeyError au chargement du module si une LoB désigne un segment qui
    n'existe pas — un mauvais rattachement ne peut donc pas atteindre un
    livrable.
    """
    verifier_rattachements({c: g["segment_s2"] for c, g in LOB_CONFIG.items()},
                           origine="A7 LOB_CONFIG")
    for cfg in LOB_CONFIG.values():
        cfg["sigma_eiopa"] = SEGMENTS_S2[cfg["segment_s2"]].sigma_reserve


_appliquer_table_officielle()


# ─────────────────────────────────────────────────────────────────────────────
#  FONCTIONS UTILITAIRES
# ─────────────────────────────────────────────────────────────────────────────

def get_lob_config(lob: str) -> Dict[str, Any]:
    """
    Retourne la configuration pour une LoB donnée.
    Fallback sur 'generique' si la LoB n'est pas reconnue.

    Parameters
    ----------
    lob : str
        Identifiant de la ligne d'activité.
        Exemples : 'mrh', 'rc_auto_corporels', 'construction'

    Returns
    -------
    Dict[str, Any]
        Configuration complète de la LoB.
    """
    cfg = LOB_CONFIG.get(lob)
    if cfg is None:
        import warnings
        warnings.warn(
            f"LoB '{lob}' non reconnue — fallback sur configuration générique. "
            f"LoB disponibles : {list(LOB_CONFIG.keys())}",
            UserWarning,
            stacklevel=2,
        )
        cfg = LOB_CONFIG["generique"].copy()
        cfg["label"] = f"Branche '{lob}' (configuration générique appliquée)"
    return cfg


def get_segment_s2(lob: str) -> SegmentS2:
    """Le segment officiel dont relève la LoB — annexe, numéro, libellé, σ.

    C'est l'accesseur qui porte la traçabilité : il rend disponible jusqu'aux
    livrables l'annexe et le numéro de segment, et pas seulement le chiffre.
    """
    return SEGMENTS_S2[get_lob_config(lob)["segment_s2"]]


def reference_s2(lob: str) -> str:
    """Référence à citer dans un livrable : « Annexe XIV, segment 2 — ... ».

    Les rapports affichaient « Annexe II » EN DUR, ce qui devenait faux dès
    qu'une LoB relevait de la santé non-SLT (annexe XIV). Le libellé est
    fabriqué par le module partagé, pour qu'A7 et A10 citent à l'identique.
    """
    return libelle_reference(get_lob_config(lob)["segment_s2"])


def get_sigma_eiopa(lob: str) -> float:
    """
    Retourne σ(réserve) du segment Solvabilité II dont relève la LoB.

    C'est bien l'écart type du risque de RÉSERVE, et non celui du risque de
    primes : l'article 117(2) fait tendre σ_s vers σ_réserve quand la mesure
    de volume des primes est nulle, ce qui est le cas d'un agent qui
    provisionne des sinistres déjà survenus. Cf. l'en-tête de SEGMENTS_S2.

    Parameters
    ----------
    lob : str
        Identifiant de la LoB.

    Returns
    -------
    float
        σ(LoB) tel que SCR_prov(LoB) = 3 × σ(LoB) × BE(LoB) — art. 115.
    """
    return get_segment_s2(lob).sigma_reserve


def list_lobs() -> list:
    """Retourne la liste des LoB disponibles (hors 'generique')."""
    return [k for k in LOB_CONFIG.keys() if k != "generique"]
