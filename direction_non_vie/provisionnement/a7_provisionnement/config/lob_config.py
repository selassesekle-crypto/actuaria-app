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
#    · facteurs EIOPA pour le SCR provisions (Art. 105 S2)
#    · LR marché de référence (source FFA/FFSA)
#
# =============================================================================

from typing import Dict, Any

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTES EIOPA — Facteurs de volatilité SCR provisions Non-Vie
#  Source : Annexe II du Règlement Délégué (UE) 2015/35, Art. 105
#  σ(LoB) utilisé dans : SCR_prov(LoB) = 3 × σ(LoB) × BE(LoB)
# ─────────────────────────────────────────────────────────────────────────────
SIGMA_EIOPA: Dict[str, float] = {
    # LoB 1 — Frais médicaux
    "frais_medicaux":               0.05,
    # LoB 2 — Protection du revenu
    "protection_revenu":            0.10,
    # LoB 3 — Indemnisation des travailleurs
    "indemnisation_travailleurs":   0.11,
    # LoB 4 — RC Auto (corporels et matériels)
    "rc_auto":                      0.08,
    # LoB 5 — Auto (dommages)
    "auto_dommages":                0.07,
    # LoB 6 — Marine, aviation, transport
    "marine_aviation_transport":    0.17,
    # LoB 7 — Incendie et autres dommages aux biens (MRH, RC Générale courte)
    "incendie_dommages":            0.10,
    # LoB 8 — RC Générale (hors auto)
    "rc_generale":                  0.11,
    # LoB 9 — Crédit et cautionnement
    "credit_cautionnement":         0.19,
    # LoB 10 — Protection juridique
    "protection_juridique":         0.05,
    # LoB 11 — Assistance
    "assistance":                   0.22,
    # LoB 12 — Pertes pécuniaires diverses
    "pertes_pecuniaires":           0.20,
    # LoB spécifiques France
    "rc_auto_corporels":            0.08,   # sous-branche RC Auto, queue très longue
    "rc_medicale":                  0.11,   # RC professionnelle médicale
    "rc_decennale":                 0.11,   # Construction décennale
    "mrh":                          0.10,   # Multirisque Habitation
}

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
        "sigma_eiopa":      SIGMA_EIOPA["auto_dommages"],
        "lob_eiopa":        "auto_dommages",

        # Longueur de développement attendue
        "queue_attendue_ans": 5,

        # Seuils H2 adaptés : Auto matériel = portefeuille stable, peu de variance
        "h2_seuil_cv":      0.12,   # CV max acceptable des facteurs
        "h2_seuil_derive":  0.15,   # dérive temporelle max acceptable

        # H1 : seuil corrélation Spearman pour alerte
        "h1_seuil_corr":    0.50,

        # Méthodes prioritaires (ordre de confiance décroissant)
        "methodes_prioritaires": ["chain_ladder", "mack_1993", "bootstrap_odp"],
        "methode_par_defaut":    "chain_ladder",

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

        # Tail factor — Guide IA 2023 (pratique professionnelle française)
        "risque_long":              True,  # Transport = risque long, seuil 1.05
        "tail_seuil_stabilisation": 1.05,   # seuil de stabilisation LDF

        # Tail factor — Guide IA 2023 (pratique professionnelle française)
        "risque_long":              True,  # RC Médicale = risque très long (20-30 ans)
        "tail_seuil_stabilisation": 1.10,   # seuil de stabilisation LDF

        # Tail factor — Guide IA 2023 (pratique professionnelle française)
        "risque_long":              True,  # RC Générale = risque long, seuil 1.05
        "tail_seuil_stabilisation": 1.05,   # seuil de stabilisation LDF

        # Tail factor — Guide IA 2023 (pratique professionnelle française)
        "risque_long":              False,  # MRH = risque court (< 4 ans)
        "tail_seuil_stabilisation": 1.01,   # seuil de stabilisation LDF

        # Tail factor — Guide IA 2023 (pratique professionnelle française)
        "risque_long":              True,  # RC Auto Corporels = risque long (15-25 ans)
        "tail_seuil_stabilisation": 1.10,   # seuil de stabilisation LDF

        # Tail factor — Guide IA 2023 : applicable uniquement si risque long
        # ET coefficients non stabilisés (dernier LDF > tail_seuil_stabilisation)
        "risque_long":              True,  # Transport = risque long (8 ans)
                                                        "tail_seuil_stabilisation": 1.05,  # LDF < 1.05 = développement très faible = stabilisé

        # Tail factor — Guide IA 2023 : applicable uniquement si risque long
        # ET coefficients non stabilisés (dernier LDF > tail_seuil_stabilisation)
        "risque_long":              True,  # RC Médicale = risque très long (20-30 ans)
        "tail_seuil_stabilisation": 1.03,  # dernier LDF min pour appliquer tail

        # Tail factor — Guide IA 2023 : applicable uniquement si risque long
        # ET coefficients non stabilisés (dernier LDF > tail_seuil_stabilisation)
        "risque_long":              True,  # RC Générale = risque long (10-15 ans)
        "tail_seuil_stabilisation": 1.02,  # dernier LDF min pour appliquer tail

        # Tail factor — Guide IA 2023 : applicable uniquement si risque long
        # ET coefficients non stabilisés (dernier LDF > tail_seuil_stabilisation)
        "risque_long":              False,  # MRH = risque court (< 4 ans)
        "tail_seuil_stabilisation": 1.01,  # dernier LDF min pour appliquer tail

        # Tail factor — Guide IA 2023 : applicable uniquement si risque long
        # ET coefficients non stabilisés (dernier LDF > tail_seuil_stabilisation)
        "risque_long":              True,  # RC Auto Corporels = risque long (15-25 ans)
        "tail_seuil_stabilisation": 1.03,  # dernier LDF min pour appliquer tail

        # Tail factor — Guide IA 2023 : applicable uniquement si risque long
        # ET coefficients non stabilisés (dernier LDF > tail_seuil_stabilisation)
        "risque_long":              False,  # RC Auto Matériel = risque court (< 5 ans)
        "tail_seuil_stabilisation": 1.01,  # dernier LDF min pour appliquer tail
    },

    # ── RC Automobile — corporels (queue très longue) ─────────────────────────
    "rc_auto_corporels": {
        "label":            "RC Automobile — Corporels",
        "sigma_eiopa":      SIGMA_EIOPA["rc_auto_corporels"],
        "lob_eiopa":        "rc_auto",

        "queue_attendue_ans": 20,

        # Queue longue → plus de tolérance sur le CV, mais surveiller la dérive
        "h2_seuil_cv":      0.20,
        "h2_seuil_derive":  0.25,
        "h1_seuil_corr":    0.50,

        "methodes_prioritaires": [
            "mack_1993", "bornhuetter_ferguson", "bootstrap_odp", "chain_ladder"
        ],
        "methode_par_defaut": "mack_1993",
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
        "sigma_eiopa":      SIGMA_EIOPA["mrh"],
        "lob_eiopa":        "incendie_dommages",

        "queue_attendue_ans": 4,

        # MRH = portefeuille très stable → seuils stricts
        "h2_seuil_cv":      0.12,
        "h2_seuil_derive":  0.12,
        "h1_seuil_corr":    0.45,

        "methodes_prioritaires": ["chain_ladder", "bootstrap_odp", "mack_1993"],
        "methode_par_defaut":    "chain_ladder",
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

        # Tail factor — Guide IA 2023 (pratique professionnelle française)
        "risque_long":              False,  # MRH = risque court (< 4 ans)
        "tail_seuil_stabilisation": 1.01,
    },

    # ── RC Générale (queue moyenne) ───────────────────────────────────────────
    "rc_generale": {
        "label":            "Responsabilité Civile Générale",
        "sigma_eiopa":      SIGMA_EIOPA["rc_generale"],
        "lob_eiopa":        "rc_generale",

        "queue_attendue_ans": 12,

        "h2_seuil_cv":      0.18,
        "h2_seuil_derive":  0.20,
        "h1_seuil_corr":    0.50,

        "methodes_prioritaires": [
            "bornhuetter_ferguson", "cape_cod", "mack_1993", "bootstrap_odp"
        ],
        "methode_par_defaut": "bornhuetter_ferguson",
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
        "sigma_eiopa":      SIGMA_EIOPA["rc_medicale"],
        "lob_eiopa":        "rc_generale",

        "queue_attendue_ans": 25,

        # Très longue queue → tolérance haute sur CV
        "h2_seuil_cv":      0.25,
        "h2_seuil_derive":  0.30,
        "h1_seuil_corr":    0.55,

        "methodes_prioritaires": [
            "bornhuetter_ferguson", "mack_1993", "cape_cod", "bootstrap_odp"
        ],
        "methode_par_defaut": "bornhuetter_ferguson",
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
        "sigma_eiopa":      SIGMA_EIOPA["rc_decennale"],
        "lob_eiopa":        "rc_generale",

        "queue_attendue_ans": 15,

        # Triangles souvent creux (déclaration différée jusqu'à 10 ans)
        "h2_seuil_cv":      0.25,
        "h2_seuil_derive":  0.25,
        "h1_seuil_corr":    0.55,

        "methodes_prioritaires": [
            "bornhuetter_ferguson", "cape_cod", "mack_1993"
        ],
        "methode_par_defaut": "bornhuetter_ferguson",
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
        "sigma_eiopa":      SIGMA_EIOPA["marine_aviation_transport"],
        "lob_eiopa":        "marine_aviation_transport",

        "queue_attendue_ans": 8,

        "h2_seuil_cv":      0.22,
        "h2_seuil_derive":  0.22,
        "h1_seuil_corr":    0.50,

        "methodes_prioritaires": [
            "bornhuetter_ferguson", "cape_cod", "mack_1993", "bootstrap_odp"
        ],
        "methode_par_defaut": "bornhuetter_ferguson",
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

    # ── Générique (fallback si lob non spécifié) ──────────────────────────────
    "generique": {
        "label":            "Branche Non-Vie Générique",
        "sigma_eiopa":      SIGMA_EIOPA["rc_generale"],
        "lob_eiopa":        "rc_generale",

        "queue_attendue_ans": 10,

        # Seuils standards marché
        "h2_seuil_cv":      0.15,
        "h2_seuil_derive":  0.20,
        "h1_seuil_corr":    0.50,

        "methodes_prioritaires": [
            "chain_ladder", "mack_1993", "bornhuetter_ferguson",
            "cape_cod", "bootstrap_odp"
        ],
        "methode_par_defaut": "chain_ladder",
        "munich_cl_disponible": False,

        "lr_marche_reference":  None,
        "lr_marche_source":     "Aucun benchmark disponible — à calibrer sur données internes",

        "alertes_specifiques": [
            "Branche non identifiée. Les seuils H2 génériques (CV=15%, dérive=20%) "
            "sont appliqués. Préciser le paramètre 'lob' pour une analyse adaptée.",
        ],

        "tail_factor_max_alerte": 1.05,

        # Tail factor — Guide IA 2023 (pratique professionnelle française)
        "risque_long":              True,   # Générique = prudence maximale
        "tail_seuil_stabilisation": 1.02,   # LDF < 1.02 = développement quasi nul

        # Tail factor — Guide IA 2023 : generique traité comme risque long par prudence
        "risque_long":              True,   # par prudence
                "tail_seuil_stabilisation": 1.1,  # prudence maximale — branche inconnue

        # Tail factor — Guide IA 2023 : applicable uniquement si risque long
        # ET coefficients non stabilisés (dernier LDF > tail_seuil_stabilisation)
        "risque_long":              True,  # Générique = prudence, traité comme risque long
        "tail_seuil_stabilisation": 1.02,  # dernier LDF min pour appliquer tail
    },
}

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


def get_sigma_eiopa(lob: str) -> float:
    """
    Retourne le facteur de volatilité σ(LoB) EIOPA pour le calcul SCR.

    Parameters
    ----------
    lob : str
        Identifiant de la LoB.

    Returns
    -------
    float
        σ(LoB) tel que SCR_prov(LoB) = 3 × σ(LoB) × BE(LoB)
    """
    cfg = get_lob_config(lob)
    return cfg["sigma_eiopa"]


def list_lobs() -> list:
    """Retourne la liste des LoB disponibles (hors 'generique')."""
    return [k for k in LOB_CONFIG.keys() if k != "generique"]
