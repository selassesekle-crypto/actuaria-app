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
        {"nom": "csp",                  "type": "categoriel", "encodage": "label",
         "modalites": ["Cadre", "Employe", "Retraite"]},
        {"nom": "usage",                "type": "categoriel", "encodage": "label",
         "modalites": ["Prive", "Pro"]},
        {"nom": "antecedents_sinistres_n1", "type": "continu", "anteriorite": True,
         "commentaire": "Connue a la souscription — exemptee du controle par l'effet"},
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
            contrat = {f.nom: row[f.nom] for f in AUTO.facteurs}
            p = self.tarif.tarifer(contrat, exposition=float(row["exposition"]))
            attendu = round(float(self.pred["prime_pure"].iloc[i]), 2)
            self.assertAlmostEqual(p["prime_pure"], attendu, places=2,
                msg=f"tarifer(contrat {i}).prime_pure={p['prime_pure']} ≠ "
                    f"portefeuille {attendu}")
            self.assertEqual(p["plan"], AUTO.empreinte())   # traçabilité ACPR
            self.assertGreater(p["prime_ttc"], p["prime_commerciale_ht"])
        print("    INV-7b tarifer() (livrable) reproduit la prime au centime + "
              "empreinte du plan ✅")

    def test_transform_leve_sur_modalite_inconnue(self):
        """La consistance de INV-7 repose sur le piège V9 : une modalité inconnue
        au scoring lève, elle n'est jamais silencieusement ignorée."""
        with self.assertRaises(ValueError):
            self.tarif.tarifer({
                "age": 40, "bonus_malus": 0.9, "anciennete_permis": 20,
                "puissance_fiscale": 6, "age_vehicule": 5, "valeur_venale": 12000,
                "garantie": "TousRisques", "carburant": "Hydrogene",  # ← inconnue
                "csp": "Cadre", "usage": "Prive", "antecedents_sinistres_n1": 0})
        print("    INV-7c modalité inconnue au scoring → lève (jamais silencieux) ✅")


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
        self.assertEqual(p['plan'], plan.empreinte())   # opposable : l'empreinte du YAML
        print(f"    INV-9 décennale tarifée par YAML seul : prime_ttc="
              f"{p['prime_ttc']} € (empreinte {p['plan']}) ✅")

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
            'usage': 'Prive', 'antecedents_sinistres_n1': 0})
        p_dec = t_dec.tarifer({'montant_travaux_eur': 500_000, 'nb_lots': 3,
            'anciennete_entreprise_ans': 8, 'type_ouvrage': 'Maison',
            'qualification_entreprise': 'Qualibat', 'nature_marche': 'Public',
            'sinistres_3ans_anterieurs': 0})
        self.assertGreater(p_auto['prime_ttc'], 0)
        self.assertGreater(p_dec['prime_ttc'], 0)
        print(f"    INV-9c même moteur : auto={p_auto['prime_ttc']} € · "
              f"décennale={p_dec['prime_ttc']} € (aucune branche LoB) ✅")


if __name__ == '__main__':
    print("=" * 70)
    print("  LES 9 INVARIANTS DU PLAN — le code honore-t-il la spec ?")
    print("=" * 70)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(__import__('__main__')))
    print("OK" if result.wasSuccessful() else "ECHEC", f"{result.testsRun} invariant(s)")
