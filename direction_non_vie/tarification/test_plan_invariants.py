"""
ActuarIA — Les 9 INVARIANTS du plan d'exécution (plan_execution_6_actions.md)
═══════════════════════════════════════════════════════════════════════════════

C'est la SPEC. Si un invariant ne passe pas, le code est faux — pas l'invariant.

Pour chaque garde-fou, deux invariants : ce qu'il doit ATTRAPER, et ce qu'il ne
doit JAMAIS casser. Le second (INV-3, INV-4) n'avait jamais été écrit — c'est lui
qui a produit B5, B7 et B9.

  | #      | Attrape                                                          |
  | INV-1  | contrat A2→A3 rompu (les 9 variables perdues)                    |
  | INV-2  | facteur déclaré détruit (B5, B7)                                 |
  | INV-3  | le plan ne doit pas neutraliser la CJUE (contrôle NÉGATIF)       |
  | INV-4  | le plan ne doit pas neutraliser l'anti-fuite (contrôle NÉGATIF)  |
  | INV-5  | B8 (un GLM ne pouvait jamais être certifié)                      |
  | INV-6  | B9 (spécification ou métrique divergente)                        |
  | INV-7  | la fonction de scoring ne reproduit pas le modèle               |
  | INV-8  | déséquilibre technique (les +7 % actuels)                        |
  | INV-9  | le test de vérité de l'architecture                             |

Discipline : chaque invariant est d'abord exécuté sur le code ACTUEL et doit
ÉCHOUER (sauf INV-3 et INV-4, contrôles négatifs qui passent d'emblée).
"""
import json
import os
import sys
import unittest
import tempfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from core.plan_tarifaire import PlanTarifaire, Facteur

TMP = tempfile.mkdtemp(prefix='actuaria_plan_inv_')


# ═══════════════════════════════════════════════════════════════════════════════
#  PLANS DE RÉFÉRENCE — reproduits depuis exemple_plans_auto_et_decennale.py
# ═══════════════════════════════════════════════════════════════════════════════
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
        # csp : one_hot (CORRECTIF — était label, nominale, le label inversait
        # Cadre/Employe). usage reste label : binaire (2 modalités) → label ≡ one-hot.
        {"nom": "csp",                  "type": "categoriel", "encodage": "one_hot",
         "modalites": ["Cadre", "Employe", "Retraite"], "reference": "Cadre"},
        {"nom": "usage",                "type": "categoriel", "encodage": "label",
         "modalites": ["Prive", "Pro"]},
        {"nom": "antecedents_sinistres_n1", "type": "continu", "anteriorite": True,
         "commentaire": "Connue a la souscription — exemptee du controle par l'effet"},
        # Colonnes DÉRIVÉES (calculées par A2, mêmes formules que _feature_engineering),
        # déclarées comme facteurs ordinaires — cf. plans/auto.yaml.
        {"nom": "jeune_conducteur",     "type": "binaire"},
        {"nom": "senior_conducteur",    "type": "binaire"},
        {"nom": "vehicule_recent",      "type": "binaire"},
        {"nom": "vehicule_ancien",      "type": "binaire"},
        {"nom": "risque_historique",    "type": "continu"},
        {"nom": "km_par_an_normalise",  "type": "continu"},
        {"nom": "milieu_geographique",  "type": "categoriel", "encodage": "label",
         "modalites": ["Urbain", "Periurbain", "Rural"]},
    ],
    "interactions": [["age", "bonus_malus"]],
})

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
         "modalites": ["Qualibat", "Non qualifie"], "reference": "Non qualifie"},
        {"nom": "nature_marche",           "type": "categoriel", "encodage": "label",
         "modalites": ["Prive", "Public"]},
        {"nom": "sinistres_3ans_anterieurs", "type": "continu", "anteriorite": True},
    ],
})

# MRH — sur-ensemble strict de l'ancien VARS_GLM['mrh'] (miroir de plans/mrh.yaml).
MRH = PlanTarifaire.depuis_dict({
    "lob": "mrh", "version": "1.0", "auteur": "S. Sekle, IA",
    "exposition": "exposition",
    "cible_frequence": "nb_sinistres", "cible_cout": "cout_total_sinistres",
    "facteurs": [
        {"nom": "surface_m2",     "type": "continu"},
        {"nom": "etage",          "type": "continu"},
        {"nom": "alarme",         "type": "binaire"},
        {"nom": "double_vitrage", "type": "binaire"},
        {"nom": "garantie_vol",   "type": "binaire"},
        {"nom": "zone_geographique", "type": "categoriel", "encodage": "label",
         "modalites": ["Urbaine", "Periurbaine", "Rurale"]},
        {"nom": "statut_occupation", "type": "categoriel", "encodage": "one_hot",
         "modalites": ["Proprietaire", "Locataire"], "reference": "Proprietaire"},
        {"nom": "type_logement",  "type": "categoriel", "encodage": "one_hot",
         "modalites": ["Maison", "Appartement"], "reference": "Maison"},
        # Dérivées calculées par A2 (mêmes formules que _feature_engineering).
        {"nom": "valeur_par_m2",  "type": "continu"},
        {"nom": "age_logement",   "type": "continu"},
        {"nom": "logement_ancien", "type": "binaire"},
    ],
})

# RC Pro — sur-ensemble strict des 4 réelles + forme_juridique ET ca_annuel_eur
# en AJOUTS DE MODÉLISATION (facteurs jamais consommés par l'ancien VARS_GLM).
# Miroir de rcpro.yaml.
RCPRO = PlanTarifaire.depuis_dict({
    "lob": "rcpro", "version": "1.0", "auteur": "S. Sekle, IA",
    "exposition": "exposition",
    "cible_frequence": "nb_sinistres", "cible_cout": "cout_total_sinistres",
    "facteurs": [
        {"nom": "nb_salaries",                "type": "continu"},
        {"nom": "anciennete_entreprise_ans",  "type": "continu"},
        {"nom": "antecedents_sinistres_3ans", "type": "continu", "anteriorite": True},
        # AJOUT DE MODÉLISATION — chiffre d'affaires (facteur RC Pro standard,
        # jamais consommé par l'ancien VARS_GLM). transformation:log -> produit
        # ca_annuel_eur + log_ca_annuel_eur. Miroir de rcpro.yaml.
        {"nom": "ca_annuel_eur", "type": "continu", "transformation": "log"},
        # secteur_activite : one_hot (CORRECTIF de modélisation — était label, une
        # variable nominale que le label-encoding écrasait). Cf. rcpro.yaml.
        {"nom": "secteur_activite", "type": "categoriel", "encodage": "one_hot",
         "modalites": ["Conseil", "BTP", "Commerce", "Industrie"], "reference": "Conseil"},
        {"nom": "type_garantie", "type": "categoriel", "encodage": "one_hot",
         "modalites": ["Base", "Etendue"], "reference": "Base"},
        # AJOUT DE MODÉLISATION (nouveau facteur, cf. rcpro.yaml).
        {"nom": "forme_juridique", "type": "categoriel", "encodage": "one_hot",
         "modalites": ["SARL", "SAS", "SA", "EI"], "reference": "SARL"},
    ],
})


# ═══════════════════════════════════════════════════════════════════════════════
#  FIXTURES — portefeuilles SAINS (signal actuariel net, aucune fuite)
# ═══════════════════════════════════════════════════════════════════════════════
def portefeuille_auto(n=4000, seed=1):
    """Portefeuille auto sain : la fréquence dépend de facteurs LÉGITIMES
    (age, bonus_malus, garantie, antécédents), le coût est Gamma, l'exposition
    est réellement dispersée. Aucune variable ne « connaît » la cible."""
    rng = np.random.default_rng(seed)
    age = rng.integers(18, 85, n).astype(float)
    bonus_malus = np.clip(rng.normal(0.9, 0.25, n), 0.5, 3.5)
    anciennete_permis = np.clip(age - 18 - rng.integers(0, 4, n), 0, None).astype(float)
    puissance_fiscale = rng.integers(4, 15, n).astype(float)
    age_vehicule = rng.integers(0, 20, n).astype(float)
    valeur_venale = np.clip(rng.normal(15000, 6000, n), 1000, None)
    garantie = rng.choice(['Tiers', 'TousRisques'], n, p=[0.4, 0.6])
    carburant = rng.choice(['Essence', 'Diesel', 'Electrique'], n, p=[0.5, 0.4, 0.1])
    csp = rng.choice(['Cadre', 'Employe', 'Retraite'], n)
    usage = rng.choice(['Prive', 'Pro'], n, p=[0.8, 0.2])
    antecedents = rng.poisson(0.15, n).astype(float)
    # Colonnes SOURCES BRUTES des indicateurs dérivés du groupe B (A2 calcule
    # ensuite km_par_an_normalise et milieu_geographique_enc).
    kilometrage_annuel = np.clip(rng.normal(12000, 4000, n), 1000, None)
    milieu_geographique = rng.choice(['Urbain', 'Periurbain', 'Rural'], n, p=[0.5, 0.3, 0.2])
    expo = np.clip(rng.beta(5, 1, n), 0.1, 1.0)
    lin = (-2.1
           + 0.9 * np.log(bonus_malus)
           + 0.7 * (age < 25).astype(float)
           + 0.02 * puissance_fiscale
           + 0.28 * (garantie == 'TousRisques').astype(float)
           + 0.30 * antecedents)
    lam = np.exp(lin)
    nb = rng.poisson(lam * expo).astype(float)
    cout = np.where(nb > 0, rng.gamma(2.0, 1200.0, n), 0.0)
    return pd.DataFrame({
        'exposition': expo,
        'age': age, 'bonus_malus': bonus_malus,
        'anciennete_permis': anciennete_permis,
        'puissance_fiscale': puissance_fiscale, 'age_vehicule': age_vehicule,
        'valeur_venale': valeur_venale, 'garantie': garantie,
        'carburant': carburant, 'csp': csp, 'usage': usage,
        'antecedents_sinistres_n1': antecedents,
        'kilometrage_annuel': kilometrage_annuel,
        'milieu_geographique': milieu_geographique,
        'nb_sinistres': nb, 'cout_total_sinistres': cout,
    })


def portefeuille_decennale(n=4000, seed=2):
    """Portefeuille décennale — LoB INCONNUE du code. Sert au test de vérité."""
    rng = np.random.default_rng(seed)
    montant = np.clip(rng.lognormal(12.5, 0.8, n), 20_000, None)
    nb_lots = rng.integers(1, 12, n).astype(float)
    anciennete = rng.integers(0, 30, n).astype(float)
    type_ouvrage = rng.choice(['Maison', 'Collectif', 'Tertiaire'], n, p=[0.5, 0.3, 0.2])
    qualif = rng.choice(['Qualibat', 'Non qualifie'], n, p=[0.7, 0.3])
    nature = rng.choice(['Prive', 'Public'], n, p=[0.6, 0.4])
    sin_ant = rng.poisson(0.1, n).astype(float)
    expo = np.clip(rng.beta(5, 1, n), 0.1, 1.0)
    lin = (-3.0
           + 0.35 * np.log(montant / 100_000)
           + 0.05 * nb_lots
           - 0.03 * anciennete
           + 0.5 * (qualif == 'Non qualifie').astype(float)
           + 0.4 * sin_ant)
    lam = np.exp(lin)
    nb = rng.poisson(lam * expo).astype(float)
    cout = np.where(nb > 0, rng.gamma(2.0, 9000.0, n), 0.0)
    return pd.DataFrame({
        'exposition': expo,
        'montant_travaux_eur': montant, 'nb_lots': nb_lots,
        'anciennete_entreprise_ans': anciennete, 'type_ouvrage': type_ouvrage,
        'qualification_entreprise': qualif, 'nature_marche': nature,
        'sinistres_3ans_anterieurs': sin_ant,
        'nb_sinistres': nb, 'cout_total_sinistres': cout,
    })


def portefeuille_mrh(n=3000, seed=3):
    """Portefeuille MRH sain — colonnes SOURCES brutes ; A2 dérive valeur_par_m2,
    age_logement, logement_ancien."""
    rng = np.random.default_rng(seed)
    surface = np.clip(rng.normal(80, 30, n), 15, None)
    statut = rng.choice(['Proprietaire', 'Locataire'], n, p=[0.6, 0.4])
    annee = rng.integers(1950, 2020, n)
    expo = np.clip(rng.beta(5, 1, n), 0.1, 1.0)
    lin = (-2.4 + 0.004 * (2026 - annee)
           + 0.3 * (statut == 'Locataire').astype(float)
           - 0.002 * surface)
    nb = rng.poisson(np.exp(lin) * expo).astype(float)
    cout = np.where(nb > 0, rng.gamma(2.0, 1500.0, n), 0.0)
    return pd.DataFrame({
        'exposition': expo, 'surface_m2': surface,
        'etage': rng.integers(0, 10, n).astype(float),
        'alarme': rng.integers(0, 2, n).astype(float),
        'double_vitrage': rng.integers(0, 2, n).astype(float),
        'garantie_vol': rng.integers(0, 2, n).astype(float),
        'zone_geographique': rng.choice(['Urbaine', 'Periurbaine', 'Rurale'], n),
        'statut_occupation': statut,
        'type_logement': rng.choice(['Maison', 'Appartement'], n),
        'valeur_mobilier': np.clip(rng.normal(25000, 10000, n), 2000, None),
        'annee_construction': annee,
        'nb_sinistres': nb, 'cout_total_sinistres': cout,
    })


def portefeuille_rcpro(n=3000, seed=5):
    """Portefeuille RC Pro sain — colonnes SOURCES brutes (aucune dérivée : RC Pro
    n'a pas de branche derivée dans A2)."""
    rng = np.random.default_rng(seed)
    nb_sal = rng.integers(1, 200, n).astype(float)
    secteur = rng.choice(['BTP', 'Conseil', 'Commerce', 'Industrie'], n)
    forme = rng.choice(['SARL', 'SAS', 'SA', 'EI'], n, p=[0.4, 0.3, 0.1, 0.2])
    ant = rng.poisson(0.3, n).astype(float)
    expo = np.clip(rng.beta(5, 1, n), 0.1, 1.0)
    lin = (-1.7 + 0.003 * nb_sal + 0.4 * ant
           + 0.3 * (secteur == 'BTP').astype(float)
           + 0.2 * (forme == 'EI').astype(float))
    nb = rng.poisson(np.exp(lin) * expo).astype(float)
    cout = np.where(nb > 0, rng.gamma(2.0, 4000.0, n), 0.0)
    return pd.DataFrame({
        'exposition': expo, 'nb_salaries': nb_sal,
        'anciennete_entreprise_ans': rng.integers(0, 30, n).astype(float),
        'antecedents_sinistres_3ans': ant,
        'ca_annuel_eur': np.clip(rng.lognormal(13, 1, n), 50000, None),
        'secteur_activite': secteur, 'type_garantie': rng.choice(['Base', 'Etendue'], n),
        'forme_juridique': forme,
        'nb_sinistres': nb, 'cout_total_sinistres': cout,
    })


def _a2(**kw):
    from direction_non_vie.tarification.a2_preprocessing.agent import AgentA2Preprocessing
    return AgentA2Preprocessing(models_path=TMP, audit_path=TMP, verbose=False, **kw)


# ═══════════════════════════════════════════════════════════════════════════════
#  INV-1 — le contrat A2 → A3 : plan.colonnes_produites() ⊆ transform(df).columns
# ═══════════════════════════════════════════════════════════════════════════════
class TestINV1_ContratA2A3(unittest.TestCase):
    """
    INV-1 — Le contrat A2→A3 se vérifie à CHAQUE transform.

        plan.colonnes_produites() ⊆ set(A2.fit(df, plan).transform(df).columns)

    Attrape : le contrat A2→A3 rompu — les 9 variables perdues, en silence,
    parce que A2 produisait 'garantie_tousrisques' (one-hot) là où A3 attendait
    'garantie_enc' (label). Avec fit/transform pilotés par le plan, A2 produit
    EXACTEMENT ce que le plan annonce, ou lève.
    """

    def test_auto_transform_produit_toutes_les_colonnes_du_plan(self):
        df = portefeuille_auto(n=800)
        a2 = _a2().fit(df, AUTO)
        out = a2.transform(df)
        attendues = set(AUTO.colonnes_produites())
        manquantes = attendues - set(out.columns)
        self.assertEqual(
            manquantes, set(),
            f"A2.transform n'a pas produit les colonnes déclarées : {sorted(manquantes)}. "
            f"Le contrat A2→A3 est rompu.")
        print(f"    INV-1a auto : {len(attendues)} colonnes du plan toutes "
              f"produites par transform ✅")

    def test_transform_sur_un_seul_contrat_produit_les_memes_colonnes(self):
        """transform doit marcher sur 1 contrat comme sur 1 million — c'est ce
        qui débloque tarifer() (INV-7)."""
        df = portefeuille_auto(n=800)
        a2 = _a2().fit(df, AUTO)
        un = df.head(1)
        out = a2.transform(un)
        attendues = set(AUTO.colonnes_produites())
        self.assertTrue(
            attendues <= set(out.columns),
            f"transform sur 1 contrat ne produit pas le plan : "
            f"{sorted(attendues - set(out.columns))}")
        print("    INV-1b transform sur 1 seul contrat : colonnes du plan "
              "complètes ✅")


# ═══════════════════════════════════════════════════════════════════════════════
#  INV-2 — un facteur déclaré n'est JAMAIS détruit (B5, B7)
#     construire_matrice_x(plan.colonnes_produites(), plan, df, cible)
#         == plan.colonnes_produites()
# ═══════════════════════════════════════════════════════════════════════════════
class TestINV2_FacteurDeclareSurvit(unittest.TestCase):
    """
    INV-2 — La liste blanche devient le plan signé. Toute colonne DÉCLARÉE et
    légitime (ni genre, ni fuite) traverse la conformité intacte.

    Attrape B5/B7 : un facteur déclaré (antecedents_sinistres_3ans, double_vitrage)
    détruit en silence par une liste blanche codée qui ne le connaissait pas.
    """

    def _mx(self, plan, df):
        from core.conformite_reglementaire import construire_matrice_x
        return construire_matrice_x(
            list(plan.colonnes_produites()), plan=plan, df=df,
            col_cible=[plan.cible_frequence, plan.cible_cout],
            contexte=f"INV-2 — {plan.lob}")

    def test_auto_toutes_les_colonnes_declarees_survivent(self):
        df = portefeuille_auto(n=3000)
        X = _a2().fit(df, AUTO).transform(df)
        mx = self._mx(AUTO, X)
        self.assertEqual(
            tuple(mx), AUTO.colonnes_produites(),
            f"Colonnes déclarées détruites : "
            f"{set(AUTO.colonnes_produites()) - set(mx)}. Exclusions : {mx.exclusions}")
        print(f"    INV-2a auto : {len(tuple(mx))} colonnes déclarées, "
              f"0 détruite ✅")

    def test_decennale_toutes_les_colonnes_declarees_survivent(self):
        df = portefeuille_decennale(n=3000)
        X = _a2().fit(df, DECENNALE).transform(df)
        mx = self._mx(DECENNALE, X)
        self.assertEqual(
            tuple(mx), DECENNALE.colonnes_produites(),
            f"Colonnes déclarées détruites : "
            f"{set(DECENNALE.colonnes_produites()) - set(mx)}. Exclusions : {mx.exclusions}")
        print(f"    INV-2b décennale : {len(tuple(mx))} colonnes déclarées "
              f"(LoB INCONNUE du code), 0 détruite ✅")

    def test_le_controle_par_l_effet_a_bien_tourne(self):
        """Le garde-fou n°4 (le seul indépendant des noms) doit avoir tourné —
        sinon la matrice n'est protégée que par le nom (insuffisant, V12)."""
        df = portefeuille_auto(n=2000)
        X = _a2().fit(df, AUTO).transform(df)
        mx = self._mx(AUTO, X)
        self.assertTrue(mx.controle_effet_execute,
                        "Le contrôle par l'effet n'a pas tourné.")
        print("    INV-2c contrôle par l'effet exécuté (df + cible fournis) ✅")


# ═══════════════════════════════════════════════════════════════════════════════
#  INV-3 & INV-4 — CONTRÔLES NÉGATIFS : le plan AUTORISE, il ne DISPENSE pas.
#  Ces deux invariants doivent PASSER D'EMBLÉE. S'ils échouent au premier essai,
#  le plan a neutralisé un garde-fou — c'est un défaut, pas un test à corriger.
# ═══════════════════════════════════════════════════════════════════════════════
class TestINV3_GenreDeclareResteBloque(unittest.TestCase):
    """
    INV-3 — Une colonne de genre DÉCLARÉE dans le plan est QUAND MÊME rejetée.
    Le plan ne doit pas pouvoir neutraliser la CJUE C-236/09 (Test-Achats).
    """

    def test_sexe_declare_dans_le_plan_est_exclu(self):
        from core.conformite_reglementaire import construire_matrice_x
        df = portefeuille_auto(n=1500)
        df['sexe'] = np.where(df['age'] % 2 == 0, 1.0, 0.0)   # genre numérique
        plan = PlanTarifaire.depuis_dict({
            "lob": "auto_genre", "exposition": "exposition",
            "cible_frequence": "nb_sinistres", "cible_cout": "cout_total_sinistres",
            "facteurs": [
                {"nom": "age", "type": "continu"},
                {"nom": "bonus_malus", "type": "continu"},
                {"nom": "sexe", "type": "continu"},   # ← DÉCLARÉ, et pourtant...
            ],
        })
        self.assertIn("sexe", plan.colonnes_produites(),
                      "Pré-condition : le plan déclare bien 'sexe'.")
        X = _a2().fit(df, plan).transform(df)
        mx = construire_matrice_x(
            list(plan.colonnes_produites()), plan=plan, df=X,
            col_cible=[plan.cible_frequence, plan.cible_cout], contexte="INV-3")
        self.assertNotIn("sexe", set(mx),
            "'sexe' déclaré dans le plan a traversé la conformité — la CJUE est "
            "neutralisée par le plan. INTERDIT.")
        self.assertIn("sexe", mx.exclusions, "L'exclusion doit être tracée.")
        self.assertIn("C-236/09", mx.exclusions["sexe"])
        print("    INV-3 'sexe' déclaré dans le plan → quand même exclu "
              "(CJUE non contournable) ✅")

    def test_proxy_civilite_declare_est_exclu(self):
        """Même un proxy (civilité) déclaré est bloqué."""
        from core.conformite_reglementaire import construire_matrice_x
        df = portefeuille_auto(n=1500)
        df['titre'] = np.where(df['age'] % 2 == 0, 1.0, 0.0)
        plan = PlanTarifaire.depuis_dict({
            "lob": "auto_titre", "exposition": "exposition",
            "cible_frequence": "nb_sinistres", "cible_cout": "cout_total_sinistres",
            "facteurs": [{"nom": "age", "type": "continu"},
                         {"nom": "titre", "type": "continu"}],
        })
        X = _a2().fit(df, plan).transform(df)
        mx = construire_matrice_x(
            list(plan.colonnes_produites()), plan=plan, df=X,
            col_cible=[plan.cible_frequence, plan.cible_cout], contexte="INV-3")
        self.assertNotIn("titre", set(mx),
            "Le proxy de genre 'titre' (civilité) déclaré a traversé la conformité.")
        print("    INV-3b proxy 'titre' (civilité) déclaré → exclu ✅")


class TestINV4_FuiteDeclareeResteBloquee(unittest.TestCase):
    """
    INV-4 — Une fuite DÉCLARÉE dans le plan est QUAND MÊME rejetée par l'EFFET.
    Le plan ne doit pas pouvoir neutraliser l'anti-fuite. Le contrôle par l'effet
    (le seul indépendant du nom) rattrape ce que le nom ne peut pas trancher.
    """

    def test_fuite_a_nom_innocent_declaree_est_rejetee_par_l_effet(self):
        from core.conformite_reglementaire import construire_matrice_x
        df = portefeuille_auto(n=3000)
        # Fuite à NOM INNOCENT : une « note interne » qui EST la sinistralité
        # observée (corrélation ~1). Le nom ne la trahit pas — seul l'effet.
        rng = np.random.default_rng(7)
        df['note_dossier_interne'] = (df['cout_total_sinistres']
                                      + rng.normal(0, 1.0, len(df)))
        plan = PlanTarifaire.depuis_dict({
            "lob": "auto_fuite", "exposition": "exposition",
            "cible_frequence": "nb_sinistres", "cible_cout": "cout_total_sinistres",
            "facteurs": [
                {"nom": "age", "type": "continu"},
                {"nom": "bonus_malus", "type": "continu"},
                {"nom": "note_dossier_interne", "type": "continu"},  # ← fuite déclarée
            ],
        })
        self.assertIn("note_dossier_interne", plan.colonnes_produites())
        X = _a2().fit(df, plan).transform(df)
        mx = construire_matrice_x(
            list(plan.colonnes_produites()), plan=plan, df=X,
            col_cible=[plan.cible_frequence, plan.cible_cout], contexte="INV-4")
        self.assertNotIn("note_dossier_interne", set(mx),
            "Une fuite (corrélation ~1 avec la cible) DÉCLARÉE dans le plan a "
            "traversé : le contrôle par l'effet a été neutralisé par le plan.")
        self.assertIn("note_dossier_interne", mx.exclusions)
        self.assertIn("FUITE", mx.exclusions["note_dossier_interne"].upper())
        print("    INV-4 fuite à nom innocent déclarée → rejetée par l'effet ✅")

    def test_les_facteurs_legitimes_ne_sont_pas_faussement_exclus(self):
        """Symétrie : le contrôle ne doit pas sur-réagir. Les facteurs sains
        déclarés (age, bonus_malus) restent, seule la fuite part."""
        from core.conformite_reglementaire import construire_matrice_x
        df = portefeuille_auto(n=3000)
        rng = np.random.default_rng(8)
        df['note_dossier_interne'] = (df['cout_total_sinistres']
                                      + rng.normal(0, 1.0, len(df)))
        plan = PlanTarifaire.depuis_dict({
            "lob": "auto_fuite2", "exposition": "exposition",
            "cible_frequence": "nb_sinistres", "cible_cout": "cout_total_sinistres",
            "facteurs": [{"nom": "age", "type": "continu"},
                         {"nom": "bonus_malus", "type": "continu"},
                         {"nom": "note_dossier_interne", "type": "continu"}],
        })
        X = _a2().fit(df, plan).transform(df)
        mx = construire_matrice_x(
            list(plan.colonnes_produites()), plan=plan, df=X,
            col_cible=[plan.cible_frequence, plan.cible_cout], contexte="INV-4")
        self.assertEqual({"age", "bonus_malus"}, set(mx),
                         f"Faux positif du contrôle par l'effet : {set(mx)}")
        print("    INV-4b aucun faux positif : les facteurs sains survivent ✅")


# ═══════════════════════════════════════════════════════════════════════════════
#  INV-5 — chaque FAMILLE peut être certifiée VERT sur un portefeuille sain (B8)
# ═══════════════════════════════════════════════════════════════════════════════
def _famille_disponible(nom):
    """Retourne (True, None) si la famille est constructible dans cet
    environnement, (False, motif) sinon. On SKIP proprement (jamais en silence)
    les familles dont la librairie n'est pas installée."""
    nl = nom.lower()
    if nl in ('dl', 'deep_learning', 'mlp'):
        try:
            import torch  # noqa: F401
            return True, None
        except Exception as e:
            return False, f"torch absent ({type(e).__name__})"
    from direction_non_vie.tarification.a4_ml.agent import creer_modele_ml_pour_nom
    try:
        creer_modele_ml_pour_nom(nl, 'nb_sinistres')
        return True, None
    except (ImportError, ModuleNotFoundError) as e:
        return False, f"librairie absente ({e})"
    except ValueError as e:
        return False, f"non recalibrable ({e})"


class TestINV5_ChaqueFamilleCertifiable(unittest.TestCase):
    """
    INV-5 — Pour chaque famille (GLM Poisson/Gamma/Tweedie, GBM, XGB, LGBM, DL),
    ∃ un portefeuille sain → VERT.

    Attrape B8 : « un GLM ne pouvait JAMAIS être certifié VERT » — le walk-forward
    ne savait recalibrer qu'un proxy sklearn, donc modele_recalibre_fidele=False,
    donc plafond AMBRE, structurellement, pour le livrable PRINCIPAL de la Non-Vie.

    ⚠ Cet invariant a été CORRIGÉ par le commit V14 (80ab69e) — postérieur à la
    rédaction du plan. Il passe donc AUJOURD'HUI. Le test reste néanmoins réel :
    la sous-méthode `test_le_gate_refuse_une_recalibration_infidele` prouve qu'il
    DISCRIMINE (une recalibration infidèle — le cas B8 — n'obtient PAS de VERT).
    """
    FAMILLES = [
        ('GLM_POISSON', 'GLM de fréquence — référence Non-Vie'),
        ('GLM_GAMMA',   'GLM de coût moyen'),
        ('GLM_TWEEDIE', 'GLM de prime pure'),
        ('gbm',         'Gradient Boosting'),
        ('xgboost',     'XGBoost'),
        ('lightgbm',    'LightGBM'),
        ('DL',          'Deep Learning (A5)'),
    ]

    def _a6(self):
        from direction_non_vie.tarification.a6_comparaison.agent import AgentA6Comparaison
        return AgentA6Comparaison(models_path=TMP, audit_path=TMP, verbose=False)

    @staticmethod
    def _backtest_sain(nom, fidele=True):
        return {'disponible': True, 'modele_recalibre_fidele': fidele,
                'modele_recalibre': nom,
                'gini_wf_moyen': 0.30, 'ae_ratio': 1.00, 'ae_moyen_wf': 1.00,
                'n_fenetres_rouge': 0, 'stabilite_wf': '🟢 Stable'}

    def test_chaque_famille_disponible_obtient_un_VERT(self):
        a6 = self._a6()
        testees, skippees = [], []
        for nom, desc in self.FAMILLES:
            dispo, motif = _famille_disponible(nom)
            if not dispo:
                skippees.append(f"{nom} ({motif})")
                continue
            modele = {'score_global': 0.95, 'gini_test': 0.32, 'modele': nom}
            statut = a6._calculer_statut_rag(
                modele, [modele], profil_valide_par='Actuaire responsable',
                environnement='production', backtest=self._backtest_sain(nom))
            self.assertEqual(statut, 'VERT',
                f"Famille '{nom}' ({desc}) : un portefeuille sain (score 0,95 · "
                f"Gini 0,32 · walk-forward fidèle et impeccable) doit obtenir un "
                f"VERT. Statut={statut}.")
            testees.append(nom)
        self.assertTrue(testees, "Aucune famille testable dans cet environnement.")
        print(f"    INV-5 familles certifiées VERT : {testees}")
        if skippees:
            print(f"    INV-5 familles SKIPPÉES (lib absente, NON silencieux) : "
                  f"{skippees}")

    def test_le_gate_refuse_une_recalibration_infidele(self):
        """Anti-vacuité + c'est EXACTEMENT B8 : une recalibration walk-forward
        INFIDÈLE (le GLM retombé sur un proxy GBM) ne doit PAS obtenir un VERT.
        Si ce test échoue, le gate accepte n'importe quoi et INV-5 ne prouve rien."""
        a6 = self._a6()
        modele = {'score_global': 0.95, 'gini_test': 0.32, 'modele': 'GLM_POISSON'}
        statut = a6._calculer_statut_rag(
            modele, [modele], profil_valide_par='Actuaire responsable',
            environnement='production',
            backtest=self._backtest_sain('GLM_POISSON', fidele=False))
        self.assertNotEqual(statut, 'VERT',
            "Une recalibration INFIDÈLE (proxy) a obtenu un VERT — le gate "
            "n'exige pas que le walk-forward porte sur le modèle retenu.")
        print(f"    INV-5b recalibration infidèle (B8) → {statut}, pas VERT "
              f"(le gate discrimine) ✅")

    # ── INV-5 renforcé : le GLM de coût est de la FAMILLE DÉCLARÉE au plan ────
    def _plan_severite(self, famille):
        d = {"lob": f"auto_{famille}", "exposition": "exposition",
             "cible_frequence": "nb_sinistres", "cible_cout": "cout_total_sinistres",
             "facteurs": [
                 {"nom": "age", "type": "continu", "transformation": "carre"},
                 {"nom": "bonus_malus", "type": "continu"},
                 {"nom": "garantie", "type": "categoriel", "encodage": "one_hot",
                  "modalites": ["Tiers", "TousRisques"], "reference": "Tiers"},
                 {"nom": "antecedents_sinistres_n1", "type": "continu",
                  "anteriorite": True}]}
        if famille is not None:
            d["famille_severite"] = famille
        return PlanTarifaire.depuis_dict(d)

    def test_famille_severite_declaree_est_reellement_ajustee(self):
        """Le champ famille_severite du plan pilote RÉELLEMENT la famille du GLM
        de coût moyen — plus de Gamma codé en dur (extension du schéma)."""
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        df = portefeuille_auto(n=4000, seed=3)
        for famille in ("gamma", "lognormal", "inverse_gaussienne"):
            with self.subTest(famille=famille):
                tarif = pipeline_complet(df, self._plan_severite(famille))
                self.assertEqual(tarif.glm_cout.famille_severite, famille,
                    f"Le plan déclare famille_severite='{famille}' mais le GLM de "
                    f"coût ajusté est '{tarif.glm_cout.famille_severite}'.")
                p = tarif.tarifer({"age": 40, "bonus_malus": 0.9,
                                   "garantie": "TousRisques",
                                   "antecedents_sinistres_n1": 0.0})
                self.assertGreater(p["prime_ttc"], 0)
        # défaut : gamma quand non déclaré (aucune LoB existante ne change)
        tarif_defaut = pipeline_complet(df, self._plan_severite(None))
        self.assertEqual(tarif_defaut.glm_cout.famille_severite, "gamma")
        print("    INV-5c famille_severite (gamma/lognormal/inverse_gaussienne) "
              "réellement ajustée par le pipeline · défaut=gamma ✅")

    def test_les_familles_de_severite_produisent_des_couts_differents(self):
        """Preuve que la famille n'est pas ignorée : trois familles → trois
        prédictions de coût moyen distinctes sur le même contrat."""
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        df = portefeuille_auto(n=4000, seed=4)
        contrat = {"age": 30, "bonus_malus": 1.1, "garantie": "TousRisques",
                   "antecedents_sinistres_n1": 1.0}
        couts = {}
        for famille in ("gamma", "lognormal", "inverse_gaussienne"):
            tarif = pipeline_complet(df, self._plan_severite(famille))
            couts[famille] = tarif.tarifer(contrat)["cout_moyen"]
        self.assertEqual(len(set(couts.values())), 3,
            f"Les familles de sévérité devraient donner des coûts distincts : {couts}")
        print(f"    INV-5d trois familles → trois coûts moyens distincts : "
              f"{ {k: round(v) for k, v in couts.items()} } ✅")


# ═══════════════════════════════════════════════════════════════════════════════
#  INV-6 — stabilité temporelle : |gini_wf − gini_test| / gini_test < 0,40  (B9)
# ═══════════════════════════════════════════════════════════════════════════════
class TestINV6_StabiliteWalkForward(unittest.TestCase):
    """
    INV-6 — Le Gini walk-forward et le Gini de test sont proches (< 40 % d'écart
    relatif). Attrape B9 : une spécification ou une métrique divergente entre les
    deux mesures.

    ⚠ Comme INV-5, cet invariant a été traité par des cycles ANTÉRIEURS au plan
    (V6 a corrigé le signe du Gini walk-forward, V11 le gate qui n'en lisait pas
    le résultat) : sur le pipeline réel, l'écart vaut ~0,33 aujourd'hui. La
    version plan ci-dessous va plus loin — elle rend B9 STRUCTURELLEMENT
    inexprimable : le Gini de test et le Gini walk-forward passent par la MÊME
    fonction (gini_lorenz) et la MÊME spécification (le pipeline plan). Deux
    mesures qui partagent leur code ne peuvent plus diverger.
    """

    def test_gini_walk_forward_proche_du_gini_test(self):
        from direction_non_vie.tarification.pipeline_tarifaire import (
            evaluer_stabilite_temporelle)
        for seed in (1, 3, 7):
            with self.subTest(seed=seed):
                df = portefeuille_auto(n=8000, seed=seed)
                r = evaluer_stabilite_temporelle(df, AUTO, n_fenetres=4)
                self.assertGreater(r["gini_wf"], 0,
                    f"Gini walk-forward ≤ 0 ({r['gini_wf']}) — signe inversé ? (B9)")
                self.assertLess(r["ecart_relatif"], 0.40,
                    f"Écart relatif {r['ecart_relatif']:.3f} ≥ 0,40 : le "
                    f"walk-forward diverge du test (gini_test={r['gini_test']:.3f}, "
                    f"gini_wf={r['gini_wf']:.3f}).")
        print("    INV-6 |gini_wf − gini_test|/gini_test < 0,40 sur 3 graines, "
              "Gini WF positif ✅")

    def test_une_metrique_divergente_serait_detectee(self):
        """Anti-vacuité : si le walk-forward mesurait avec une métrique DIVERGENTE
        (le symptôme réel de B9 : signe du Gini inversé), l'écart relatif
        exploserait au-delà de 0,40 et l'invariant échouerait. C'est ce qui rend
        INV-6 réel."""
        from direction_non_vie.tarification.pipeline_tarifaire import (
            evaluer_stabilite_temporelle)
        df = portefeuille_auto(n=8000, seed=3)
        r = evaluer_stabilite_temporelle(df, AUTO, n_fenetres=4)
        self.assertLess(r["ecart_relatif"], 0.40)          # métrique cohérente : OK
        gini_wf_divergent = -r["gini_test"]                # métrique divergente (B9)
        ecart_divergent = abs(gini_wf_divergent - r["gini_test"]) / abs(r["gini_test"])
        self.assertGreater(ecart_divergent, 0.40,
            "Une métrique divergente doit faire échouer INV-6 — sinon il ne teste rien.")
        print(f"    INV-6b métrique cohérente : écart {r['ecart_relatif']:.3f} < 0,40 ; "
              f"métrique divergente (B9) : écart {ecart_divergent:.2f} > 0,40 → "
              f"détectée ✅")


# ═══════════════════════════════════════════════════════════════════════════════
#  INV-7 — tarifer(contrat_i) ≈ prédiction_portefeuille[i]  à 1e-6  (étape 5)
# ═══════════════════════════════════════════════════════════════════════════════
class TestINV7_TariferReproduitLeModele(unittest.TestCase):
    """
    INV-7 — La fonction de scoring reproduit le modèle. tarifer() appliqué à un
    contrat du portefeuille doit rendre, à 1e-6, la prédiction du portefeuille.
    Sinon transform() diverge de fit() (le piège V9 : recalculer les modalités).
    C'est ce qui débloque le livrable commercial (« tarifez-moi ce contrat »).
    """

    def setUp(self):
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        self.df = portefeuille_auto(n=4000, seed=5)
        self.tarif = pipeline_complet(self.df, AUTO)
        self.pred = self.tarif.predire_portefeuille(self.df)

    def test_scoring_unitaire_reproduit_le_portefeuille_a_1e6(self):
        """transform sur 1 contrat == transform sur le portefeuille, pour ce
        contrat. C'est l'invariance au lot : la clé de INV-7."""
        maxdiff = 0.0
        for i in (0, 1, 100, 1000, 2500, 3999):
            solo = self.tarif.predire_portefeuille(self.df.iloc[[i]])["prime_pure"].iloc[0]
            porte = self.pred["prime_pure"].iloc[i]
            maxdiff = max(maxdiff, abs(solo - porte))
        self.assertLess(maxdiff, 1e-6,
            f"tarifer/predire sur 1 contrat diverge du portefeuille de {maxdiff:.2e} "
            f"(> 1e-6) : transform() ne reproduit pas fit().")
        print(f"    INV-7a scoring unitaire = portefeuille à {maxdiff:.1e} "
              f"(< 1e-6) ✅")

    def test_tarifer_livrable_reproduit_au_centime(self):
        for i in (0, 42, 1500, 3999):
            row = self.df.iloc[i]
            # Contrat = colonnes SOURCES BRUTES du portefeuille (A2 dérive
            # jeune_conducteur, km_par_an_normalise… — elles ne sont pas saisies).
            contrat = row.to_dict()
            p = self.tarif.tarifer(contrat, exposition=float(row["exposition"]))
            attendu = round(float(self.pred["prime_pure"].iloc[i]), 2)
            self.assertAlmostEqual(p["prime_pure"], attendu, places=2,
                msg=f"tarifer(contrat {i}).prime_pure={p['prime_pure']} ≠ "
                    f"portefeuille {attendu}")
            self.assertEqual(p["plan_empreinte"], AUTO.empreinte())   # traçabilité ACPR
            self.assertGreater(p["prime_ttc"], p["prime_commerciale_ht"])
        print("    INV-7b tarifer() (livrable) reproduit la prime au centime + "
              "empreinte du plan ✅")

    def test_modalite_inconnue_est_capturee_pas_ignoree(self):
        """La consistance de INV-7 repose sur le piège V9 : une modalité inconnue
        au scoring n'est JAMAIS silencieusement ignorée. Depuis le contrat de
        sortie stable (API), elle est CAPTURÉE — success:False + erreur nommant la
        modalité fautive — plutôt que propagée en exception brute."""
        res = self.tarif.tarifer({
            "age": 40, "bonus_malus": 0.9, "anciennete_permis": 20,
            "puissance_fiscale": 6, "age_vehicule": 5, "valeur_venale": 12000,
            "garantie": "TousRisques", "carburant": "Hydrogene",  # ← inconnue
            "csp": "Cadre", "usage": "Prive", "antecedents_sinistres_n1": 0,
            "kilometrage_annuel": 12000, "milieu_geographique": "Urbain"})
        self.assertEqual(res["success"], False)
        self.assertIn("Hydrogene", res["erreur"])   # la modalité fautive est nommée
        self.assertIsInstance(json.dumps(res), str)  # l'erreur reste sérialisable
        print("    INV-7c modalité inconnue → capturée (success:False, erreur "
              "nommant la modalité), jamais silencieuse ✅")


# ═══════════════════════════════════════════════════════════════════════════════
#  INV-8 — équilibre technique : Σ primes_pures ≈ Σ charge_observée  à ±1%
# ═══════════════════════════════════════════════════════════════════════════════
class TestINV8_EquilibreTechnique(unittest.TestCase):
    """
    INV-8 — La prime pure totale reproduit la charge totale à ±1 %. Attrape le
    déséquilibre technique (les « +7 % » actuels) : un GLM de prime pure produit
    par le PRODUIT de deux GLM (fréquence × coût) n'est pas mécaniquement calé
    en niveau. Le coefficient d'équilibre k = Σ charge / Σ prime_pure prédite le
    ramène dans la bande.
    """

    def test_equilibre_a_1pct_apres_calage(self):
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        for seed in (1, 3, 5):
            with self.subTest(seed=seed):
                df = portefeuille_auto(n=6000, seed=seed)
                charge = float(df["cout_total_sinistres"].sum())
                tarif = pipeline_complet(df, AUTO, equilibrer=True)
                somme = float(tarif.predire_portefeuille(df)["prime_pure"].sum())
                ecart = abs(somme / charge - 1.0)
                self.assertLess(ecart, 0.01,
                    f"Déséquilibre technique {ecart*100:.2f}% > 1 % : "
                    f"Σprime={somme:.0f} vs Σcharge={charge:.0f}.")
        print("    INV-8a Σ primes_pures ≈ Σ charge à ±1 % (3 graines) ✅")

    def test_l_equilibrage_corrige_un_desequilibre_reel(self):
        """Anti-vacuité : sans calage, le déséquilibre brut (le produit fréquence
        × coût) sort de la bande. C'est exactement le « +7 % » que INV-8 corrige —
        si le brut était déjà à ±1 %, k ne servirait à rien et le test ne prouverait
        rien."""
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        df = portefeuille_auto(n=6000, seed=5)
        charge = float(df["cout_total_sinistres"].sum())
        brut = pipeline_complet(df, AUTO, equilibrer=False)
        cale = pipeline_complet(df, AUTO, equilibrer=True)
        ecart_brut = abs(float(brut.predire_portefeuille(df)["prime_pure"].sum()) / charge - 1)
        ecart_cale = abs(float(cale.predire_portefeuille(df)["prime_pure"].sum()) / charge - 1)
        self.assertGreater(ecart_brut, 0.01,
            "Le modèle brut est déjà équilibré — INV-8 ne prouverait rien ici.")
        self.assertLess(ecart_cale, 0.01)
        self.assertLess(ecart_cale, ecart_brut)
        print(f"    INV-8b déséquilibre brut {ecart_brut*100:.2f}% → calé "
              f"{ecart_cale*100:.2f}% (k={cale.coefficient_equilibre:.4f}) ✅")


# ═══════════════════════════════════════════════════════════════════════════════
#  INV-9 — LE TEST DE VÉRITÉ : la décennale se tarife PAR YAML SEUL
# ═══════════════════════════════════════════════════════════════════════════════
_RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))


class TestINV9_DecennaleParYamlSeul(unittest.TestCase):
    """
    INV-9 — Le test de vérité de l'architecture. Une LoB INCONNUE du moteur
    (décennale) se tarife par le SEUL fichier plans/decennale.yaml, sans toucher
    au code. Si ce test passe, les 12 LoB sont couvertes ; sinon, on a trois démos.

    « Tu n'atteindras pas les 12 LoB en ajoutant de la connaissance métier au
    moteur. Tu les atteindras en la lui retirant. »
    """

    def test_decennale_se_tarife_par_yaml_seul(self):
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        plan = PlanTarifaire.depuis_yaml(os.path.join(_RACINE, 'plans', 'decennale.yaml'))
        tarif = pipeline_complet(portefeuille_decennale(n=4000, seed=2), plan)
        p = tarif.tarifer({
            'montant_travaux_eur': 850_000, 'nb_lots': 4,
            'anciennete_entreprise_ans': 12, 'type_ouvrage': 'Collectif',
            'qualification_entreprise': 'Qualibat', 'nature_marche': 'Prive',
            'sinistres_3ans_anterieurs': 0,
        })
        self.assertGreater(p['prime_ttc'], 0,
            "La décennale ne se tarife pas par YAML seul — l'architecture n'y est pas.")
        self.assertEqual(p['plan_empreinte'], plan.empreinte())   # opposable : empreinte du YAML
        print(f"    INV-9 décennale tarifée par YAML seul : prime_ttc="
              f"{p['prime_ttc']} € (empreinte {p['plan_empreinte']}) ✅")

    def test_le_moteur_ne_contient_aucune_connaissance_decennale(self):
        """La preuve que « sans toucher au code » est vraie : aucun fichier du
        MOTEUR ne mentionne un terme spécifique à la décennale. La LoB vit
        ENTIÈREMENT dans le YAML."""
        moteur = [
            os.path.join(_RACINE, 'core', 'plan_tarifaire.py'),
            os.path.join(_RACINE, 'core', 'conformite_reglementaire.py'),
            os.path.join(_RACINE, 'direction_non_vie', 'tarification',
                         'pipeline_tarifaire.py'),
        ]
        termes_decennale = ('decennale', 'montant_travaux', 'type_ouvrage',
                            'qualibat', 'qualification_entreprise', 'nb_lots',
                            'nature_marche')
        for chemin in moteur:
            with open(chemin, encoding='utf-8') as fh:
                contenu = fh.read().lower()
            for terme in termes_decennale:
                self.assertNotIn(terme, contenu,
                    f"{os.path.basename(chemin)} contient '{terme}' : le moteur "
                    f"« connaît » la décennale — l'architecture déclarative est "
                    f"contournée.")
        print("    INV-9b le moteur ne contient AUCUN terme spécifique décennale "
              "(LoB 100 % dans le YAML) ✅")

    def test_meme_moteur_pour_auto_et_decennale(self):
        """auto et décennale passent par le MÊME pipeline_complet, sans branche
        sur la LoB. C'est ce qui prouve qu'aucune connaissance métier n'est codée."""
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        plan_auto = PlanTarifaire.depuis_yaml(os.path.join(_RACINE, 'plans', 'auto.yaml'))
        plan_dec = PlanTarifaire.depuis_yaml(os.path.join(_RACINE, 'plans', 'decennale.yaml'))
        t_auto = pipeline_complet(portefeuille_auto(n=3000), plan_auto)
        t_dec = pipeline_complet(portefeuille_decennale(n=3000), plan_dec)
        p_auto = t_auto.tarifer({'age': 40, 'bonus_malus': 0.9, 'anciennete_permis': 20,
            'puissance_fiscale': 6, 'age_vehicule': 5, 'valeur_venale': 12000,
            'garantie': 'TousRisques', 'carburant': 'Diesel', 'csp': 'Cadre',
            'usage': 'Prive', 'antecedents_sinistres_n1': 0,
            'kilometrage_annuel': 12000, 'milieu_geographique': 'Urbain'})
        p_dec = t_dec.tarifer({'montant_travaux_eur': 500_000, 'nb_lots': 3,
            'anciennete_entreprise_ans': 8, 'type_ouvrage': 'Maison',
            'qualification_entreprise': 'Qualibat', 'nature_marche': 'Public',
            'sinistres_3ans_anterieurs': 0})
        self.assertGreater(p_auto['prime_ttc'], 0)
        self.assertGreater(p_dec['prime_ttc'], 0)
        print(f"    INV-9c même moteur : auto={p_auto['prime_ttc']} € · "
              f"décennale={p_dec['prime_ttc']} € (aucune branche LoB) ✅")


# ═══════════════════════════════════════════════════════════════════════════════
#  CONTRAT DE SORTIE de tarifer() — VERROU pour une future API REST/JSON
# ═══════════════════════════════════════════════════════════════════════════════
class TestContratSortieJSON(unittest.TestCase):
    """
    tarifer() renvoie un contrat de sortie STABLE et directement consommable par
    une API REST/JSON — en cas de SUCCÈS comme d'ERREUR (l'exception est capturée,
    jamais propagée brute). Ce test fige le contrat : il casse si quelqu'un
    réintroduit un numpy.float64, oublie un cast float(), ou renomme/retire
    success / plan_empreinte / date_calcul.
    """

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        cls.tarif = pipeline_complet(portefeuille_auto(n=3000), AUTO)

    @staticmethod
    def _contrat_valide():
        return {"age": 35, "bonus_malus": 0.9, "anciennete_permis": 15,
                "puissance_fiscale": 6, "age_vehicule": 5, "valeur_venale": 13000,
                "garantie": "TousRisques", "carburant": "Diesel", "csp": "Cadre",
                "usage": "Prive", "antecedents_sinistres_n1": 0,
                "kilometrage_annuel": 12000, "milieu_geographique": "Urbain"}

    def test_succes_est_json_serialisable_et_trace(self):
        res = self.tarif.tarifer(self._contrat_valide(), exposition=1.0)
        rendu = json.dumps(res)                    # lève si un type n'est pas natif
        self.assertIsInstance(rendu, str)
        self.assertEqual(res["success"], True)
        self.assertIn("plan_empreinte", res)
        self.assertIn("date_calcul", res)
        self.assertEqual(res["plan_empreinte"], AUTO.empreinte())
        for k, v in res.items():                   # aucun numpy/pandas caché
            self.assertEqual(type(v).__module__, "builtins",
                             f"clé '{k}' de type non natif {type(v)}")
        print("    CONTRAT succès : json.dumps OK · success/plan_empreinte/"
              "date_calcul présents · 100% natif ✅")

    def test_erreur_est_capturee_et_json_serialisable(self):
        # contrat AMPUTÉ d'une colonne requise → tarifer() capture l'exception
        incomplet = self._contrat_valide()
        del incomplet["garantie"]
        res = self.tarif.tarifer(incomplet, exposition=1.0)
        rendu = json.dumps(res)                     # doit réussir aussi sur l'erreur
        self.assertIsInstance(rendu, str)
        self.assertEqual(res["success"], False)
        self.assertIn("erreur", res)
        self.assertIsInstance(res["erreur"], str)
        self.assertIn("plan_empreinte", res)
        self.assertIn("date_calcul", res)
        for k, v in res.items():
            self.assertEqual(type(v).__module__, "builtins",
                             f"clé '{k}' de type non natif {type(v)}")
        print("    CONTRAT erreur : exception capturée → {success:False, erreur} "
              "json-sérialisable et tracé ✅")


# ═══════════════════════════════════════════════════════════════════════════════
#  MRH — 2e LoB tarifée par plan déclaratif (sur-ensemble strict de VARS_GLM['mrh'])
# ═══════════════════════════════════════════════════════════════════════════════
class TestMRH_PlanDeclaratif(unittest.TestCase):
    """
    MRH tarifée par le plan déclaratif — sur-ensemble STRICT de l'ancien
    VARS_GLM['mrh'] (0 perte réelle : les 2 références mortes type_logement_enc /
    statut_occupation_enc, remplacées par les vrais one-hot). Même méthode que
    l'auto, LoB différente : la vérification empirique a confirmé ses spécificités
    propres (colonnes mortes différentes, année de référence corrigée).
    """

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        cls.df = portefeuille_mrh(n=3000)
        cls.tarif = pipeline_complet(cls.df, MRH)

    def test_transform_produit_les_colonnes_du_plan(self):
        X = _a2().fit(self.df, MRH).transform(self.df)
        manquantes = set(MRH.colonnes_produites()) - set(X.columns)
        self.assertEqual(manquantes, set(),
            f"MRH INV-1 rompu : colonnes manquantes {sorted(manquantes)}")
        print(f"    MRH INV-1 : {len(MRH.colonnes_produites())} colonnes du plan "
              f"toutes produites par transform ✅")

    def test_tarifer_mrh_json(self):
        res = self.tarif.tarifer({
            'surface_m2': 75, 'etage': 2, 'alarme': 1, 'double_vitrage': 1,
            'garantie_vol': 1, 'zone_geographique': 'Urbaine',
            'statut_occupation': 'Locataire', 'type_logement': 'Appartement',
            'valeur_mobilier': 30000, 'annee_construction': 1990})
        self.assertEqual(res['success'], True)
        self.assertGreater(res['prime_ttc'], 0)
        self.assertIsInstance(json.dumps(res), str)
        print(f"    MRH tarifer() : success, prime_ttc={res['prime_ttc']} € ✅")

    def test_age_logement_suit_l_annee_d_execution(self):
        """Correctif du bug « 2024 codé en dur » : age_logement = année COURANTE −
        annee_construction. Le test calcule l'attendu avec LA MÊME fonction
        datetime.now().year — vrai quel que soit l'an où il tourne (et il
        échouerait si le code figeait encore 2024)."""
        from datetime import datetime
        X = _a2().fit(self.df, MRH).transform(self.df)
        annee = datetime.now().year
        attendu = annee - self.df['annee_construction'].astype(int).to_numpy()
        obtenu = X['age_logement'].astype(int).to_numpy()
        self.assertTrue((obtenu == attendu).all(),
            "age_logement ne suit pas datetime.now().year (2024 encore codé en dur ?)")
        print(f"    MRH age_logement = {annee} − annee_construction (année "
              f"dynamique, plus de 2024 codé en dur) ✅")


# ═══════════════════════════════════════════════════════════════════════════════
#  RC Pro — 3e LoB par plan déclaratif + AJOUT DE MODÉLISATION (forme_juridique)
# ═══════════════════════════════════════════════════════════════════════════════
class TestRCPro_PlanDeclaratif(unittest.TestCase):
    """
    RC Pro tarifée par plan déclaratif — sur-ensemble STRICT des 4 facteurs RÉELS
    de VARS_GLM['rcpro'] (la ref morte type_garantie_enc remplacée par le vrai
    one-hot). RC Pro n'a AUCUNE dérivée (aucune modif d'A2). PLUS un AJOUT DE
    MODÉLISATION distinct : forme_juridique, jamais consommé par l'ancien code
    (encodé par A2 mais absent de VARS_GLM — un oubli), désormais déclaré.
    """

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        cls.df = portefeuille_rcpro(n=3000)
        cls.tarif = pipeline_complet(cls.df, RCPRO)

    def test_transform_produit_les_colonnes_du_plan(self):
        X = _a2().fit(self.df, RCPRO).transform(self.df)
        manquantes = set(RCPRO.colonnes_produites()) - set(X.columns)
        self.assertEqual(manquantes, set(),
            f"RC Pro INV-1 rompu : colonnes manquantes {sorted(manquantes)}")
        print(f"    RC Pro INV-1 : {len(RCPRO.colonnes_produites())} colonnes du "
              f"plan toutes produites par transform ✅")

    def test_forme_juridique_entre_dans_le_modele(self):
        """L'AJOUT DE MODÉLISATION : forme_juridique (jamais consommé avant) est
        maintenant une colonne du plan ET une feature conforme du GLM."""
        cols_fj = [c for c in RCPRO.colonnes_produites()
                   if c.startswith('forme_juridique_')]
        self.assertTrue(cols_fj, "forme_juridique n'a produit aucune colonne")
        self.assertTrue(set(cols_fj) <= set(self.tarif.features),
            "forme_juridique déclaré mais écarté des features conformes du GLM")
        print(f"    RC Pro forme_juridique (ajout de modélisation) dans le modèle : "
              f"{cols_fj} ✅")

    def test_tarifer_rcpro_json(self):
        res = self.tarif.tarifer({
            'nb_salaries': 25, 'anciennete_entreprise_ans': 8,
            'antecedents_sinistres_3ans': 0, 'ca_annuel_eur': 1_200_000,
            'secteur_activite': 'Conseil', 'type_garantie': 'Etendue',
            'forme_juridique': 'SAS'})
        self.assertEqual(res['success'], True)
        self.assertGreater(res['prime_ttc'], 0)
        self.assertIsInstance(json.dumps(res), str)
        print(f"    RC Pro tarifer() : success, prime_ttc={res['prime_ttc']} € ✅")


# ═══════════════════════════════════════════════════════════════════════════════
#  LOT 1 (Phase 4) — 3 LoB INÉDITES tarifées par le SEUL plans/<lob>.yaml.
#  INV-1 vérifié sur l'ARTEFACT RÉEL (depuis_yaml, pas un miroir depuis_dict) : le
#  test échoue si le YAML expédié cesse de produire une seule de ses colonnes.
#  Chaîne 100 % déclarative (pipeline_complet, GLM pur), aucune connaissance LoB
#  dans le moteur — comme décennale/transport.
# ═══════════════════════════════════════════════════════════════════════════════
def portefeuille_flotte(n=3000, seed=11):
    """Flotte auto — colonnes SOURCES ; A2 dérive log_taille_flotte et
    log_valeur_moyenne_vehicule (transformation:log ; LoB inédite, aucune branche A2)."""
    rng = np.random.default_rng(seed)
    taille = rng.integers(1, 80, n).astype(float)
    typ = rng.choice(['VL', 'VUL', 'PL', 'Mixte'], n, p=[.55, .25, .12, .08])
    tele = rng.integers(0, 2, n).astype(float)
    sin2 = rng.poisson(0.4, n).astype(float)
    expo = np.clip(rng.beta(5, 1, n), 0.1, 1.0)
    lin = (-1.8 + 0.8 * (np.log(taille) - np.log(20)) + 0.45 * (typ == 'PL')
           + 0.25 * sin2 - 0.25 * tele)
    nb = rng.poisson(np.exp(lin) * expo).astype(float)
    cout = np.where(nb > 0, rng.gamma(2.0, 2500.0, n), 0.0)
    return pd.DataFrame({
        'exposition': expo, 'taille_flotte': taille,
        'valeur_moyenne_vehicule': np.clip(rng.lognormal(np.log(18000), 0.6, n), 3000, None),
        'age_moyen_flotte': rng.uniform(1, 15, n),
        'puissance_moyenne': rng.uniform(60, 200, n), 'type_flotte': typ,
        'secteur_activite': rng.choice(['Services', 'Commerce', 'BTP', 'Transport'], n),
        'zone_circulation': rng.choice(['Urbaine', 'Periurbaine', 'Rurale'], n),
        'telematique': tele, 'sinistres_2ans_anterieurs': sin2,
        'nb_sinistres': nb, 'cout_total_sinistres': cout,
    })


class TestFlotteAutomobile_PlanDeclaratif(unittest.TestCase):
    """Flotte auto — LoB INÉDITE tarifée par le seul plans/flotte_automobile.yaml
    (taille_flotte en VOLUME-log, comme nb_expeditions_an en cargo)."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        cls.plan = PlanTarifaire.depuis_yaml(
            os.path.join(_RACINE, 'plans', 'flotte_automobile.yaml'))
        cls.df = portefeuille_flotte(n=3000)
        cls.tarif = pipeline_complet(cls.df, cls.plan)

    def test_transform_produit_les_colonnes_du_plan(self):
        X = _a2().fit(self.df, self.plan).transform(self.df)
        manquantes = set(self.plan.colonnes_produites()) - set(X.columns)
        self.assertEqual(manquantes, set(),
            f"Flotte INV-1 rompu : colonnes manquantes {sorted(manquantes)}")
        print(f"    Flotte INV-1 : {len(self.plan.colonnes_produites())} colonnes du "
              f"plan toutes produites par transform ✅")

    def test_tarifer_flotte_json(self):
        res = self.tarif.tarifer({
            'taille_flotte': 20, 'valeur_moyenne_vehicule': 18000,
            'age_moyen_flotte': 6, 'puissance_moyenne': 120, 'type_flotte': 'VUL',
            'secteur_activite': 'Transport', 'zone_circulation': 'Periurbaine',
            'telematique': 1, 'sinistres_2ans_anterieurs': 0})
        self.assertEqual(res['success'], True)
        self.assertGreater(res['prime_ttc'], 0)
        self.assertIsInstance(json.dumps(res), str)
        print(f"    Flotte tarifer() : success, prime_ttc={res['prime_ttc']} € ✅")


def portefeuille_mrp(n=3000, seed=21):
    """MRP — colonnes SOURCES ; A2 dérive les log (surface/contenu/CA). LoB inédite,
    aucune branche A2 (contrairement à la MRH, sa sœur habitation)."""
    rng = np.random.default_rng(seed)
    sect = rng.choice(['Bureau', 'Commerce', 'Artisanat', 'Restauration', 'Industrie'], n)
    pinc = rng.integers(0, 2, n).astype(float)
    zone = rng.choice(['Rurale', 'Periurbaine', 'Urbaine'], n)
    sin3 = rng.poisson(0.35, n).astype(float)
    expo = np.clip(rng.beta(5, 1, n), 0.1, 1.0)
    lin = (-1.7 + 0.75 * (sect == 'Restauration') - 0.3 * pinc + 0.25 * sin3
           + 0.3 * np.select([zone == 'Periurbaine', zone == 'Urbaine'], [1., 2.], 0.))
    nb = rng.poisson(np.exp(lin) * expo).astype(float)
    cout = np.where(nb > 0, rng.gamma(2.0, 4000.0, n), 0.0)
    return pd.DataFrame({
        'exposition': expo,
        'surface_locaux_m2': np.clip(rng.lognormal(np.log(120), 0.9, n), 15, None),
        'valeur_contenu_eur': np.clip(rng.lognormal(np.log(80000), 1.0, n), 3000, None),
        'chiffre_affaires_eur': np.clip(rng.lognormal(np.log(400000), 0.9, n), 20000, None),
        'anciennete_batiment_ans': rng.uniform(0, 60, n), 'secteur_activite': sect,
        'protection_incendie': pinc, 'protection_vol': rng.integers(0, 2, n).astype(float),
        'zone_geographique': zone, 'sinistres_3ans_anterieurs': sin3,
        'nb_sinistres': nb, 'cout_total_sinistres': cout,
    })


class TestMRP_PlanDeclaratif(unittest.TestCase):
    """MRP (multirisque professionnelle) — LoB INÉDITE tarifée par le seul
    plans/multirisque_professionnelle.yaml (surface en log ; zone_geographique en
    label ordinal de risque vol, Rurale=0 → Urbaine=2)."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        cls.plan = PlanTarifaire.depuis_yaml(
            os.path.join(_RACINE, 'plans', 'multirisque_professionnelle.yaml'))
        cls.df = portefeuille_mrp(n=3000)
        cls.tarif = pipeline_complet(cls.df, cls.plan)

    def test_transform_produit_les_colonnes_du_plan(self):
        X = _a2().fit(self.df, self.plan).transform(self.df)
        manquantes = set(self.plan.colonnes_produites()) - set(X.columns)
        self.assertEqual(manquantes, set(),
            f"MRP INV-1 rompu : colonnes manquantes {sorted(manquantes)}")
        print(f"    MRP INV-1 : {len(self.plan.colonnes_produites())} colonnes du "
              f"plan toutes produites par transform ✅")

    def test_tarifer_mrp_json(self):
        res = self.tarif.tarifer({
            'surface_locaux_m2': 150, 'valeur_contenu_eur': 90000,
            'chiffre_affaires_eur': 450000, 'anciennete_batiment_ans': 25,
            'secteur_activite': 'Restauration', 'protection_incendie': 1,
            'protection_vol': 1, 'zone_geographique': 'Urbaine',
            'sinistres_3ans_anterieurs': 0})
        self.assertEqual(res['success'], True)
        self.assertGreater(res['prime_ttc'], 0)
        self.assertIsInstance(json.dumps(res), str)
        print(f"    MRP tarifer() : success, prime_ttc={res['prime_ttc']} € ✅")


def portefeuille_rcg(n=3000, seed=31):
    """RC Générale — colonnes SOURCES ; A2 dérive log_chiffre_affaires_eur et
    log_effectif. LoB inédite, aucune branche A2."""
    rng = np.random.default_rng(seed)
    sect = rng.choice(['Services', 'Commerce', 'Industrie', 'Evenementiel', 'BTP'], n)
    sst = rng.integers(0, 2, n).astype(float)
    prod = rng.choice(['Aucune', 'France', 'Export'], n, p=[.45, .40, .15])
    sin3 = rng.poisson(0.3, n).astype(float)
    expo = np.clip(rng.beta(5, 1, n), 0.1, 1.0)
    lin = (-1.8 + 0.85 * (sect == 'BTP') + 0.25 * sst + 0.3 * sin3
           + 0.3 * (prod == 'Export'))
    nb = rng.poisson(np.exp(lin) * expo).astype(float)
    cout = np.where(nb > 0, rng.gamma(2.0, 6000.0, n), 0.0)
    return pd.DataFrame({
        'exposition': expo,
        'chiffre_affaires_eur': np.clip(rng.lognormal(np.log(500000), 1.0, n), 20000, None),
        'effectif': np.clip(np.round(rng.lognormal(np.log(15), 0.9, n)), 1, None),
        'secteur_activite': sect, 'anciennete_entreprise_ans': rng.uniform(0, 40, n),
        'sous_traitance': sst, 'couverture_produits': prod,
        'sinistres_3ans_anterieurs': sin3,
        'nb_sinistres': nb, 'cout_total_sinistres': cout,
    })


class TestRCGenerale_PlanDeclaratif(unittest.TestCase):
    """RC Générale — LoB INÉDITE tarifée par le seul plans/rc_generale.yaml.
    Distincte de la RC Pro (faute professionnelle/E&O) : ici l'exploitation et les
    produits. CA = exposition primaire ; couverture_produits Export = queue de
    sévérité (prior ouvert, comme mode_transport en cargo)."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        cls.plan = PlanTarifaire.depuis_yaml(
            os.path.join(_RACINE, 'plans', 'rc_generale.yaml'))
        cls.df = portefeuille_rcg(n=3000)
        cls.tarif = pipeline_complet(cls.df, cls.plan)

    def test_transform_produit_les_colonnes_du_plan(self):
        X = _a2().fit(self.df, self.plan).transform(self.df)
        manquantes = set(self.plan.colonnes_produites()) - set(X.columns)
        self.assertEqual(manquantes, set(),
            f"RC Générale INV-1 rompu : colonnes manquantes {sorted(manquantes)}")
        print(f"    RC Générale INV-1 : {len(self.plan.colonnes_produites())} colonnes "
              f"du plan toutes produites par transform ✅")

    def test_tarifer_rcg_json(self):
        res = self.tarif.tarifer({
            'chiffre_affaires_eur': 600000, 'effectif': 20, 'secteur_activite': 'BTP',
            'anciennete_entreprise_ans': 10, 'sous_traitance': 1,
            'couverture_produits': 'Export', 'sinistres_3ans_anterieurs': 0})
        self.assertEqual(res['success'], True)
        self.assertGreater(res['prime_ttc'], 0)
        self.assertIsInstance(json.dumps(res), str)
        print(f"    RC Générale tarifer() : success, prime_ttc={res['prime_ttc']} € ✅")


# ═══════════════════════════════════════════════════════════════════════════════
#  LOT 2 (Phase 4) — 3 LoB INÉDITES de plus, mêmes garanties (INV-1 sur l'artefact
#  YAML réel + smoke tarifer(), chaîne 100 % déclarative, aucune connaissance moteur).
# ═══════════════════════════════════════════════════════════════════════════════
def portefeuille_pj(n=3000, seed=41):
    """Protection juridique — colonnes SOURCES ; A2 dérive log_seuil_intervention_eur
    et log_plafond_garantie_eur (transformation:log ; LoB inédite, aucune branche A2)."""
    rng = np.random.default_rng(seed)
    tsous = rng.choice(['Particulier', 'Profession_liberale', 'Entreprise'], n, p=[.55, .25, .20])
    dom = rng.choice(['Consommation', 'Travail', 'Voisinage', 'Immobilier', 'Contractuel'], n)
    niveau = rng.choice(['Base', 'Intermediaire', 'Etendue'], n)
    ncode = np.select([niveau == 'Intermediaire', niveau == 'Etendue'], [1., 2.], 0.)
    med = rng.integers(0, 2, n).astype(float)
    ant = rng.poisson(0.3, n).astype(float)
    expo = np.clip(rng.beta(5, 1, n), 0.1, 1.0)
    lin = (-1.6 + 0.55 * (tsous == 'Entreprise') + 0.40 * (dom == 'Travail')
           + 0.35 * ncode - 0.20 * med + 0.30 * ant)
    nb = rng.poisson(np.exp(lin) * expo).astype(float)
    cout = np.where(nb > 0, rng.gamma(2.0, 1500.0, n), 0.0)
    return pd.DataFrame({
        'exposition': expo, 'type_souscripteur': tsous, 'domaine_principal': dom,
        'niveau_couverture': niveau,
        'seuil_intervention_eur': np.clip(rng.lognormal(np.log(300), 0.5, n), 50, None),
        'plafond_garantie_eur': np.clip(rng.lognormal(np.log(15000), 0.6, n), 1000, None),
        'mediation_prealable': med, 'antecedents_litiges_2ans': ant,
        'nb_sinistres': nb, 'cout_total_sinistres': cout,
    })


class TestProtectionJuridique_PlanDeclaratif(unittest.TestCase):
    """Protection juridique — LoB INÉDITE tarifée par le seul
    plans/protection_juridique.yaml (niveau_couverture en label ordinal d'étendue ;
    seuil_intervention = paramètre de produit assumé comme facteur −fréquence)."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        cls.plan = PlanTarifaire.depuis_yaml(
            os.path.join(_RACINE, 'plans', 'protection_juridique.yaml'))
        cls.df = portefeuille_pj(n=3000)
        cls.tarif = pipeline_complet(cls.df, cls.plan)

    def test_transform_produit_les_colonnes_du_plan(self):
        X = _a2().fit(self.df, self.plan).transform(self.df)
        manquantes = set(self.plan.colonnes_produites()) - set(X.columns)
        self.assertEqual(manquantes, set(),
            f"Protection juridique INV-1 rompu : colonnes manquantes {sorted(manquantes)}")
        print(f"    Protection juridique INV-1 : {len(self.plan.colonnes_produites())} "
              f"colonnes du plan toutes produites par transform ✅")

    def test_tarifer_pj_json(self):
        res = self.tarif.tarifer({
            'type_souscripteur': 'Entreprise', 'domaine_principal': 'Travail',
            'niveau_couverture': 'Etendue', 'seuil_intervention_eur': 300,
            'plafond_garantie_eur': 20000, 'mediation_prealable': 0,
            'antecedents_litiges_2ans': 0})
        self.assertEqual(res['success'], True)
        self.assertGreater(res['prime_ttc'], 0)
        self.assertIsInstance(json.dumps(res), str)
        print(f"    Protection juridique tarifer() : success, prime_ttc={res['prime_ttc']} € ✅")


def portefeuille_bris(n=3000, seed=51):
    """Bris de machine — colonnes SOURCES ; A2 dérive log_valeur_machine_eur et
    log_heures_fonctionnement_an. LoB inédite, aucune branche A2."""
    rng = np.random.default_rng(seed)
    typ = rng.choice(['Production', 'Levage', 'Froid', 'Informatique', 'Energie'],
                     n, p=[.35, .15, .20, .15, .15])
    maint = rng.integers(0, 2, n).astype(float)
    env = rng.choice(['Interieur', 'Exterieur', 'Chantier'], n, p=[.5, .3, .2])
    sin2 = rng.poisson(0.35, n).astype(float)
    expo = np.clip(rng.beta(5, 1, n), 0.1, 1.0)
    lin = (-1.7 + 0.30 * (typ == 'Froid') + 0.50 * (env == 'Chantier')
           - 0.35 * maint + 0.30 * sin2)
    nb = rng.poisson(np.exp(lin) * expo).astype(float)
    cout = np.where(nb > 0, rng.gamma(2.0, 3000.0, n), 0.0)
    return pd.DataFrame({
        'exposition': expo,
        'valeur_machine_eur': np.clip(rng.lognormal(np.log(50000), 0.8, n), 2000, None),
        'age_machine_ans': rng.uniform(0, 25, n), 'type_machine': typ,
        'heures_fonctionnement_an': np.clip(rng.lognormal(np.log(2000), 0.6, n), 100, None),
        'maintenance_preventive': maint, 'environnement': env,
        'sinistres_2ans_anterieurs': sin2,
        'nb_sinistres': nb, 'cout_total_sinistres': cout,
    })


class TestBrisMachine_PlanDeclaratif(unittest.TestCase):
    """Bris de machine — LoB INÉDITE tarifée par le seul plans/bris_machine.yaml
    (heures_fonctionnement en intensité-log ; valeur → sévérité seule, effet
    fréquence délibérément non modélisé)."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        cls.plan = PlanTarifaire.depuis_yaml(
            os.path.join(_RACINE, 'plans', 'bris_machine.yaml'))
        cls.df = portefeuille_bris(n=3000)
        cls.tarif = pipeline_complet(cls.df, cls.plan)

    def test_transform_produit_les_colonnes_du_plan(self):
        X = _a2().fit(self.df, self.plan).transform(self.df)
        manquantes = set(self.plan.colonnes_produites()) - set(X.columns)
        self.assertEqual(manquantes, set(),
            f"Bris de machine INV-1 rompu : colonnes manquantes {sorted(manquantes)}")
        print(f"    Bris de machine INV-1 : {len(self.plan.colonnes_produites())} "
              f"colonnes du plan toutes produites par transform ✅")

    def test_tarifer_bris_json(self):
        res = self.tarif.tarifer({
            'valeur_machine_eur': 50000, 'age_machine_ans': 8, 'type_machine': 'Levage',
            'heures_fonctionnement_an': 2500, 'maintenance_preventive': 1,
            'environnement': 'Chantier', 'sinistres_2ans_anterieurs': 0})
        self.assertEqual(res['success'], True)
        self.assertGreater(res['prime_ttc'], 0)
        self.assertIsInstance(json.dumps(res), str)
        print(f"    Bris de machine tarifer() : success, prime_ttc={res['prime_ttc']} € ✅")


def portefeuille_immeuble(n=3000, seed=61):
    """Multirisque immeuble — colonnes SOURCES ; A2 dérive log_surface_totale_m2 et
    log_valeur_reconstruction_eur. LoB inédite, aucune branche A2."""
    rng = np.random.default_rng(seed)
    surface = np.clip(rng.lognormal(np.log(1500), 0.8, n), 100, None)
    valeur = surface * np.clip(rng.lognormal(np.log(1800), 0.5, n), 200, None)
    typ = rng.choice(['Habitation', 'Mixte', 'Commercial', 'Tertiaire'], n, p=[.5, .2, .15, .15])
    mat = rng.choice(['Beton', 'Brique', 'Pierre', 'Ossature_bois'], n, p=[.45, .25, .20, .10])
    comm = rng.integers(0, 2, n).astype(float)
    pinc = rng.integers(0, 2, n).astype(float)
    sin2 = rng.poisson(0.5, n).astype(float)
    expo = np.clip(rng.beta(5, 1, n), 0.1, 1.0)
    lin = (-1.4 + 0.40 * (np.log(surface) - np.log(1500)) + 0.40 * (mat == 'Ossature_bois')
           + 0.30 * comm - 0.30 * pinc + 0.30 * sin2)
    nb = rng.poisson(np.exp(lin) * expo).astype(float)
    cout = np.where(nb > 0, rng.gamma(2.0, 4500.0, n), 0.0)
    return pd.DataFrame({
        'exposition': expo, 'surface_totale_m2': surface, 'valeur_reconstruction_eur': valeur,
        'age_immeuble_ans': rng.uniform(0, 90, n), 'type_immeuble': typ,
        'materiau_construction': mat, 'presence_commerce_rdc': comm,
        'protection_incendie': pinc, 'sinistres_2ans_anterieurs': sin2,
        'nb_sinistres': nb, 'cout_total_sinistres': cout,
    })


class TestMultirisqueImmeuble_PlanDeclaratif(unittest.TestCase):
    """Multirisque immeuble — LoB INÉDITE tarifée par le seul
    plans/multirisque_immeuble.yaml. Distincte de la MRH (un logement) et de la MRP
    (locaux d'entreprise) : ici le BÂTIMENT. surface → fréquence, valeur → sévérité
    (colinéaires ~0.85, séparés par le prix/m² ; identifiabilité vérifiée)."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        cls.plan = PlanTarifaire.depuis_yaml(
            os.path.join(_RACINE, 'plans', 'multirisque_immeuble.yaml'))
        cls.df = portefeuille_immeuble(n=3000)
        cls.tarif = pipeline_complet(cls.df, cls.plan)

    def test_transform_produit_les_colonnes_du_plan(self):
        X = _a2().fit(self.df, self.plan).transform(self.df)
        manquantes = set(self.plan.colonnes_produites()) - set(X.columns)
        self.assertEqual(manquantes, set(),
            f"Multirisque immeuble INV-1 rompu : colonnes manquantes {sorted(manquantes)}")
        print(f"    Multirisque immeuble INV-1 : {len(self.plan.colonnes_produites())} "
              f"colonnes du plan toutes produites par transform ✅")

    def test_tarifer_immeuble_json(self):
        res = self.tarif.tarifer({
            'surface_totale_m2': 2000, 'valeur_reconstruction_eur': 3600000,
            'age_immeuble_ans': 40, 'type_immeuble': 'Commercial',
            'materiau_construction': 'Ossature_bois', 'presence_commerce_rdc': 1,
            'protection_incendie': 1, 'sinistres_2ans_anterieurs': 0})
        self.assertEqual(res['success'], True)
        self.assertGreater(res['prime_ttc'], 0)
        self.assertIsInstance(json.dumps(res), str)
        print(f"    Multirisque immeuble tarifer() : success, prime_ttc={res['prime_ttc']} € ✅")


# ═══════════════════════════════════════════════════════════════════════════════
#  LOT 3 (Phase 4, DERNIER) — 2 LoB INÉDITES : risques agricoles, D&O. Clôt la
#  Phase 4 (8 LoB déclaratives sur 8). Mêmes garanties : INV-1 sur l'artefact YAML
#  réel + smoke tarifer(), chaîne 100 % déclarative, aucune connaissance moteur.
# ═══════════════════════════════════════════════════════════════════════════════
def portefeuille_agri(n=3000, seed=71):
    """Risques agricoles — colonnes SOURCES ; A2 dérive log_surface_exploitation_ha
    et log_valeur_assuree_eur. LoB inédite, aucune branche A2."""
    rng = np.random.default_rng(seed)
    typ = rng.choice(['Grandes_cultures', 'Elevage', 'Viticulture', 'Maraichage', 'Polyculture'],
                     n, p=[.35, .25, .15, .10, .15])
    grele = rng.choice(['Faible', 'Moyenne', 'Forte'], n, p=[.35, .40, .25])
    gcode = np.select([grele == 'Moyenne', grele == 'Forte'], [1., 2.], 0.)
    filet = rng.integers(0, 2, n).astype(float)
    irrig = rng.integers(0, 2, n).astype(float)
    sin3 = rng.poisson(0.4, n).astype(float)
    surface = np.clip(rng.lognormal(np.log(60), 0.9, n), 2, None)
    expo = np.clip(rng.beta(5, 1, n), 0.1, 1.0)
    lin = (-1.7 + 0.50 * (np.log(surface) - np.log(60)) + 0.55 * (typ == 'Viticulture')
           + 0.40 * gcode - 0.30 * filet - 0.25 * irrig + 0.30 * sin3)
    nb = rng.poisson(np.exp(lin) * expo).astype(float)
    cout = np.where(nb > 0, rng.gamma(2.0, 4000.0, n), 0.0)
    return pd.DataFrame({
        'exposition': expo, 'surface_exploitation_ha': surface, 'type_production': typ,
        'valeur_assuree_eur': np.clip(rng.lognormal(np.log(200000), 0.8, n), 10000, None),
        'exposition_grele': grele, 'filet_anti_grele': filet, 'irrigation': irrig,
        'sinistres_climatiques_3ans': sin3,
        'nb_sinistres': nb, 'cout_total_sinistres': cout,
    })


class TestRisquesAgricoles_PlanDeclaratif(unittest.TestCase):
    """Risques agricoles — LoB multi-péril INÉDITE tarifée par le seul
    plans/risques_agricoles.yaml (surface en volume-log ; exposition_grele en label
    ordinal ; valeur → sévérité seule)."""

    @classmethod
    def setUpClass(cls):
        from direction_non_vie.tarification.pipeline_tarifaire import pipeline_complet
        cls.plan = PlanTarifaire.depuis_yaml(
            os.path.join(_RACINE, 'plans', 'risques_agricoles.yaml'))
        cls.df = portefeuille_agri(n=3000)
        cls.tarif = pipeline_complet(cls.df, cls.plan)

    def test_transform_produit_les_colonnes_du_plan(self):
        X = _a2().fit(self.df, self.plan).transform(self.df)
        manquantes = set(self.plan.colonnes_produites()) - set(X.columns)
        self.assertEqual(manquantes, set(),
            f"Risques agricoles INV-1 rompu : colonnes manquantes {sorted(manquantes)}")
        print(f"    Risques agricoles INV-1 : {len(self.plan.colonnes_produites())} "
              f"colonnes du plan toutes produites par transform ✅")

    def test_tarifer_agri_json(self):
        res = self.tarif.tarifer({
            'surface_exploitation_ha': 80, 'type_production': 'Viticulture',
            'valeur_assuree_eur': 250000, 'exposition_grele': 'Forte',
            'filet_anti_grele': 0, 'irrigation': 1, 'sinistres_climatiques_3ans': 1})
        self.assertEqual(res['success'], True)
        self.assertGreater(res['prime_ttc'], 0)
        self.assertIsInstance(json.dumps(res), str)
        print(f"    Risques agricoles tarifer() : success, prime_ttc={res['prime_ttc']} € ✅")


if __name__ == '__main__':
    print("=" * 70)
    print("  LES 9 INVARIANTS DU PLAN — le code honore-t-il la spec ?")
    print("=" * 70)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("OK" if result.wasSuccessful() else "ECHEC", f"{result.testsRun} invariant(s)")
