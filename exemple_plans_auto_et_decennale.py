"""Le PlanTarifaire tient-il ses promesses ?"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.plan_tarifaire import PlanTarifaire, Facteur

# ───────────────────────────────────────────────────────────────────────────
# AUTO — reproduit la config actuelle, mais en UNE SEULE déclaration
# ───────────────────────────────────────────────────────────────────────────
AUTO = PlanTarifaire.depuis_dict({
    "lob": "auto", "version": "1.0", "auteur": "S. Sekle, IA",
    "exposition": "exposition",
    "cible_frequence": "nb_sinistres",
    "cible_cout": "cout_total_sinistres",
    "facteurs": [
        {"nom": "age",                  "type": "continu", "transformation": "carre"},
        {"nom": "bonus_malus",          "type": "continu"},
        {"nom": "anciennete_permis",    "type": "continu"},
        {"nom": "puissance_fiscale",    "type": "continu"},
        {"nom": "age_vehicule",         "type": "continu"},
        {"nom": "valeur_venale",        "type": "continu", "transformation": "log"},
        {"nom": "garantie",             "type": "categoriel", "encodage": "one_hot",
         "modalites": ["Tiers", "TousRisques"], "reference": "Tiers"},
        {"nom": "carburant",            "type": "categoriel", "encodage": "one_hot",
         "modalites": ["Essence", "Diesel", "Electrique"], "reference": "Essence"},
        {"nom": "csp",                  "type": "categoriel", "encodage": "label",
         "modalites": ["Cadre", "Employe", "Retraite"]},
        {"nom": "usage",                "type": "categoriel", "encodage": "label",
         "modalites": ["Prive", "Pro"]},
        {"nom": "antecedents_sinistres_n1", "type": "continu", "anteriorite": True,
         "commentaire": "Connue a la souscription — exemptee du controle par l'effet"},
    ],
    "interactions": [["age", "bonus_malus"]],
})

# ───────────────────────────────────────────────────────────────────────────
# DÉCENNALE — LoB INCONNUE du module. Zéro ligne de code. Juste ceci.
# ───────────────────────────────────────────────────────────────────────────
DECENNALE = PlanTarifaire.depuis_dict({
    "lob": "decennale", "version": "1.0", "auteur": "S. Sekle, IA",
    "exposition": "exposition",
    "cible_frequence": "nb_sinistres",
    "cible_cout": "cout_total_sinistres",
    "facteurs": [
        {"nom": "montant_travaux_eur",     "type": "continu", "transformation": "log"},
        {"nom": "nb_lots",                 "type": "continu"},
        {"nom": "anciennete_entreprise_ans", "type": "continu"},
        {"nom": "type_ouvrage",            "type": "categoriel", "encodage": "one_hot",
         "modalites": ["Maison", "Collectif", "Tertiaire"], "reference": "Maison"},
        {"nom": "qualification_entreprise", "type": "categoriel", "encodage": "one_hot",
         "modalites": ["Qualibat", "Non qualifié"], "reference": "Non qualifié"},
        {"nom": "nature_marche",           "type": "categoriel", "encodage": "label",
         "modalites": ["Prive", "Public"]},
        {"nom": "sinistres_3ans_anterieurs", "type": "continu", "anteriorite": True},
    ],
})

for plan in (AUTO, DECENNALE):
    print("=" * 78)
    print(f"PLAN « {plan.lob.upper()} »   v{plan.version}   empreinte {plan.empreinte()}")
    print("=" * 78)
    print(f"  Colonnes que le FICHIER CLIENT doit contenir ({len(plan.colonnes_sources())}) :")
    print(f"    {list(plan.colonnes_sources())}")
    print(f"\n  Colonnes que A2 PRODUIRA — et que A3 ATTENDRA — et que la conformité")
    print(f"  AUTORISERA. Une seule et même liste ({len(plan.colonnes_produites())}) :")
    for c in plan.colonnes_produites():
        print(f"    · {c}")
    print(f"\n  Exemptées du contrôle par l'effet (antériorité) :")
    print(f"    {list(plan.facteurs_anteriorite()) or 'aucune'}")
    print()

print("=" * 78)
print("LE CONTRAT A2 → A3 EST-IL DÉSORMAIS IMPOSSIBLE À ROMPRE ?")
print("=" * 78)
print("  Ancien monde : A2 produisait 'garantie_tousrisques' (one-hot)")
print("                 A3 attendait  'garantie_enc'          (label)")
print("                 → 9 variables tarifaires perdues, en silence.\n")
print("  Nouveau monde : les deux appellent plan.colonnes_produites().")
print(f"                  AUTO → {[c for c in AUTO.colonnes_produites() if c.startswith('garantie')]}")
print(f"                  A2 les crée. A3 les attend. Même fonction. Même liste.")
print("\n  ✅ La désynchronisation n'est plus un bug à corriger : elle est")
print("     devenue inexprimable.")
print("=" * 78)
