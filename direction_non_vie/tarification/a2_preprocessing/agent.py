"""
╔══════════════════════════════════════════════════════════════════════════════╗
║               ACTUARIA — AGENT A2 : PREPROCESSING & FEATURE ENGINEERING     ║
║                           Version 1.0 — Production                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  RÔLE DE CET AGENT                                                           ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  L'agent A2 transforme les données brutes (sortie A1) en données            ║
║  prêtes pour la calibration des modèles actuariels (A3/A4/A5).             ║
║                                                                              ║
║  PIPELINE COMPLET :                                                          ║
║  1. NETTOYAGE APPROFONDI                                                     ║
║     Imputation valeurs manquantes · Correction types · Doublons             ║
║                                                                              ║
║  2. TRAITEMENT DES OUTLIERS                                                  ║
║     Winsorisation (méthode IQR) · Plafonnement réglementaire                ║
║                                                                              ║
║  3. ENCODAGE VARIABLES CATÉGORIELLES                                        ║
║     Weight of Evidence (WoE) · Target Encoding · One-Hot                   ║
║                                                                              ║
║  4. CALCUL DE L'EXPOSITION                                                   ║
║     Offset GLM Poisson · Fraction d'année · Validation                      ║
║                                                                              ║
║  5. FEATURE ENGINEERING MÉTIER                                               ║
║     Variables d'interaction · Variables dérivées actuarielles               ║
║     Spécifiques par sous-branche                                             ║
║                                                                              ║
║  6. VERSIONING DES TRANSFORMATIONS                                           ║
║     Sauvegarde des paramètres · Reproductibilité · Audit trail              ║
║                                                                              ║
║  AUTONOMIE : Niveau 2                                                        ║
║  L'agent choisit ses paramètres de façon autonome et justifie               ║
║  chaque décision par écrit. Il pose UNE question à l'utilisateur            ║
║  uniquement si une décision dépasse son périmètre.                          ║
║                                                                              ║
║  PRINCIPE CLÉ : Ce que A2 fait, A3 ne refait pas.                          ║
║  Les données sortant de A2 sont directement utilisables par le GLM.        ║
║                                                                              ║
║  USAGE DANS GOOGLE COLAB                                                     ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  %run '/tmp/actuaria/agents/a2_preprocessing.py'          ║
║                                                                              ║
║  agent_a2 = AgentA2Preprocessing()                                          ║
║  result   = agent_a2.run(result_a1)  # Passe le résultat de A1             ║
║                                                                              ║
║  AUTEUR   : ActuarIA — Système Actuariel IA                                 ║
║  VERSION  : 1.0                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ── IMPORTS ───────────────────────────────────────────────────────────────────
import os
import json
import logging
from datetime import datetime
from pathlib import Path
import copy
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
from core.charts_tarif import glyphe_rag

try:
    from ..services.tarif_excel import export_excel_a2
    TARIF_EXCEL_OK_A2 = True
except ImportError:
    try:
        from direction_non_vie.tarification.services.tarif_excel import export_excel_a2
        TARIF_EXCEL_OK_A2 = True
    except ImportError:
        TARIF_EXCEL_OK_A2 = False

# Filtre de conformité partagé (source unique avec A3/A4/A5/A6) — audit V9.
# Appliqué inconditionnellement aux configs d'encodage : le genre ne doit
# jamais être encodé, quelle que soit la sous-branche (CJUE C-236/09).
from core.conformite_reglementaire import filtrer_genre

# Plan de tarification déclaratif — LA SOURCE UNIQUE du contrat A2→A3 (étape 2).
# fit()/transform() (plus bas) sont pilotés par le plan et produisent EXACTEMENT
# plan.colonnes_produites() — le même _slug et les mêmes suffixes que ceux
# qu'annonce le plan, sinon le contrat A2→A3 redevient implicite.
from core.plan_tarifaire import PlanTarifaire, Facteur, _slug, _SUFFIXE_TRANSFO

# ⚠️⚠️ CONSTAT `a2/C15` — LE FILTRE GLOBAL D'AVERTISSEMENTS EST RETIRÉ.
# `warnings.filterwarnings('ignore')` posé ICI, au niveau module, s'appliquait
# au PROCESSUS ENTIER dès l'import : tout appelant de cet agent perdait les
# avertissements de TOUS ses modules, y compris ceux qu'il n'a jamais importés.
# *Une bibliothèque ne change pas l'état global du processus à l'import.*
#
# ⚠️ CE QU'IL CACHAIT, MESURÉ SUR UN RUN RÉEL (pipeline complet, 1 200 lignes) :
#     7x Pandas4Warning   `select_dtypes` — NOTRE code, rupture pandas 4
#     6x UserWarning       sklearn : « X does not have valid feature names »
#     3x FutureWarning     statsmodels : le calcul du BIC change apres 0.13
# ⚠️ Le 3e porte sur `bic`, PUBLIÉ dans les métriques d'A3 (trois sites) et au
# chapitre 1 du rapport signé. *Un nombre publié dont la définition change.*
#
# ⚠️ ET JE CORRIGE MON PROPRE SOUPÇON : je pensais y trouver des avertissements
# de NON-CONVERGENCE. Il n'y en a aucun sur ce portefeuille. Le mécanisme est
# réel, la trouvaille est ailleurs — *une hypothèse mesurée vaut mieux qu'une
# hypothèse plausible.*
#
# ⚠️ RIEN DE NOTRE CODE N'APPELLE `warnings.warn` : relevé sur tarification et
# core, zéro site. Ce qui remonte est donc TIERS, et peu volumineux.

# ── LOGGER ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('actuaria.a2')


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES DE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# Seuil Winsorisation par variable
# Justification actuarielle :
# La Winsorisation plafonne les valeurs extrêmes au percentile défini.
# Ex : prime_pure au P99 → on remplace les 1% de valeurs les plus élevées
# par la valeur du 99ème percentile. Cela évite qu'un sinistre catastrophique
# unique biaise l'estimation des paramètres du GLM Gamma.
# Valeurs calibrées sur les statistiques du marché français (FFA 2022).
# ⚠ ON NE WINSORISE JAMAIS UNE CIBLE — CORRECTIF DE MODÉLISATION.
# Ce dict contenait 'cout_total_sinistres' (0.00, 0.99), 'prime_pure',
# 'prime_commerciale' et 'cout_moyen_attendu' : des grandeurs de la FAMILLE CIBLE
# (cf. filtrer_famille_cible, core/conformite_reglementaire.py), écrasées à leur
# centile 99 avant même qu'A3 ne les voie.
#
# Winsoriser un FACTEUR est légitime : c'est de la robustesse, la variable
# explicative reste ce qu'elle est. Winsoriser une CIBLE DÉTRUIT LA CHARGE :
# l'excédent n'est pas mis de côté, il disparaît. Mesuré sur décennale 100k —
# cout_total_sinistres : max 341 997 € → 55 662 €, moyenne des sinistrés
# 39 630 € → 32 669 € : 17,6 % de la charge EFFACÉE, en silence. A3 ne voyait
# jamais les vrais coûts et sous-tarifiait de 15 % (Σ primes / Σ charge = 0,85).
# Le chemin déclaratif y échappait (A2.transform ne winsorise que les facteurs du
# plan) : la même grandeur avait donc deux traitements contradictoires.
#
# Le traitement CORRECT des sinistres graves est l'écrêtement AVEC RÉINJECTION :
# on clippe pour que quelques graves ne pilotent pas les relativités, et on
# remet l'excédent dans le tarif (prime_grave_unitaire). C'est exactement ce que
# fait construire_cible_severite (core/severite.py), désormais utilisé par A3 ET
# par pipeline_complet. Écrêter sans réinjecter, c'est écrêter les graves du
# PRIX mais pas de la RÉALITÉ.
#
# ⚠ RESTE À TRAITER (reliquat de Phase 2, hors périmètre de ce correctif) : les
# trois entrées ci-dessous sont des FACTEURS, et c'est une liste codée en dur
# SPÉCIFIQUE À UNE LoB (valeur_venale/kilometrage_annuel = auto ; ca_annuel_eur
# = rcpro). A2.fit/transform winsorise déjà les facteurs GÉNÉRIQUEMENT, depuis le
# plan (_WINSOR_Q). Cette liste doit disparaître comme VARS_CATEGORIELLES et
# INTERACTIONS avant elle.

# Variables catégorielles par sous-branche — PÉRIMÈTRE NON-VIE UNIQUEMENT
# (auto · MRH · RC Pro). Les sous-branches Vie/Épargne-Retraite et
# Santé-Prévoyance ont été RETIRÉES : chaque direction est désormais
# autonome et dispose de son propre service de données. A1/A2 sont des
# agents de la Direction Non-Vie et ne traitent que du Non-Vie.
#
# Ces variables seront encodées selon la méthode appropriée
# Justification : l'encodage WoE est préféré pour les GLM car il
# préserve la relation monotone avec la variable cible.
# Le One-Hot est utilisé pour les variables à faible cardinalité (< 5 modalités).
#
# ⚠ 'sexe' NE FIGURE VOLONTAIREMENT DANS AUCUNE LISTE D'ENCODAGE.
# Historique (audit V9, BLOQUANT) : 'sexe' était présent dans la config
# one_hot de toutes les sous-branches, et n'était retiré que pour 'auto'
# via un scoping par nom de branche. En MRH, l'encodage produisait donc
# sexe_m/sexe_f, colonnes qui atteignaient directement la matrice X d'A4
# (prouvé par exécution). Le genre est interdit en tarification pour TOUTE
# branche d'assurance (CJUE C-236/09), pas seulement en RC Auto : il n'a
# donc rien à faire dans une config d'encodage, quelle qu'elle soit.
# Depuis la Phase 2, ce constat est devenu STRUCTUREL : il n'y a plus de config
# d'encodage du tout — seul le plan déclare, et aucun plan ne déclare le genre
# (voir le bloc ci-dessous). Défense en profondeur inchangée : filtrer_genre()
# reste appliqué, non contournable, à la sélection de features d'A3/A4/A5/A6.

# ── Encodage et interactions : DÉCLARÉS PAR LE PLAN (Phase 2) ─────────────────
# VARS_CATEGORIELLES et INTERACTIONS SUPPRIMÉS — c'étaient les deux dernières
# listes codées en dur du pipeline. A2.run() reçoit le PLAN signé et produit les
# colonnes qu'il déclare, via _appliquer_facteur() : LA MÊME fonction que
# fit()/transform(). Le chemin agent et le chemin déclaratif partagent donc
# littéralement l'autorité d'encodage (one_hot vs label, ordre des modalités,
# transformations, interactions) — plus de 3ᵉ implémentation, plus de décalage
# silencieux A2/A3, et une LoB inédite (décennale, marchandises) est encodée
# correctement sans toucher une ligne de code.
#
# CONFORMITÉ — genre interdit en tarification (CJUE C-236/09, Test-Achats,
# 01/03/2011, applicable depuis le 21/12/2012 ; risque de sanction ACPR si la
# variable atteint la matrice X). ⚠ Le mécanisme de protection a CHANGÉ avec
# cette étape et il est plus fort qu'avant :
#   - AVANT : filtrer_genre() était appliqué à la config d'encodage (_encoder).
#     Historiquement, un COLS_INTERDITES_PAR_BRANCHE = {'auto': ['sexe']}
#     conditionnait même la protection au NOM de la sous-branche (audit V9,
#     BLOQUANT) — l'anti-pattern que le module de conformité condamne.
#   - MAINTENANT : A2.run n'encode QUE les facteurs déclarés au plan. Aucun plan
#     ne déclare le genre, donc aucune colonne de genre n'est encodée — la
#     protection est STRUCTURELLE, plus conditionnelle. Le repli d'encodage
#     automatique des colonnes 'object' non configurées (qui recréait 'sexe_enc'
#     par contournement) a disparu avec _encoder.
#   - DÉFENSE EN PROFONDEUR inchangée : filtrer_genre() reste appliqué, NON
#     contournable, dans construire_matrice_x() côté A3/A4/A5/A6 — y compris si
#     un plan déclarait le genre (INV-3 le prouve). Source unique :
#     core/conformite_reglementaire.py.
#
# ⚠ NOTE (audit V4, 10/07/2026) : la référence de transposition en droit
# français ("loi du 1er juillet 2012") n'a pas pu être vérifiée par une
# recherche documentaire formelle — à confirmer par un juriste avant toute
# communication externe la citant. L'arrêt
# CJUE C-236/09 et sa date d'application reposent sur une base plus robuste.

# Stratégies d'imputation par type de variable
# Justification :
# Médiane pour les variables numériques asymétriques (coûts, primes)
# → La médiane est robuste aux outliers contrairement à la moyenne
# Mode pour les variables catégorielles
# → On conserve la modalité la plus fréquente
STRATEGIES_IMPUTATION = {
    'numerique_asymetrique': 'median',   # Coûts, primes, capitaux
    'numerique_symetrique':  'mean',     # Âges, durées, expositions
    'categorielle':          'mode',     # CSP, garantie, type
    'binaire':               'mode',     # Fumeur, alarme, garanties 0/1
}

#: Les modalites d'un facteur `binaire`. Implicites, parce que le plan interdit
#: a un binaire de porter un encodage : il produit sa colonne telle quelle, il
#: n'y a donc aucune liste de modalites a declarer. C'est une definition, pas un
#: reglage -- d'ou la constante plutot qu'un litteral disperse.
_MODALITES_BINAIRES: frozenset = frozenset({0.0, 1.0})

#: La table ci-dessus dit QUOI ; celles-ci disent COMMENT et sous quel nom.
#: Les separer est ce qui permet a `_imputer` de LIRE la strategie declaree au
#: lieu de la reecrire -- le defaut `a2/C7` etait exactement l'absence de ce
#: lien.
_CALCUL_IMPUTATION = {
    'median': lambda s: s.median(),
    'mean':   lambda s: s.mean(),
    'mode':   lambda s: (s.mode().iloc[0] if not s.mode().empty else None),
}

#: Le libelle publie a l'actuaire pour chaque strategie.
_LIBELLE_IMPUTATION = {'median': 'mediane', 'mean': 'moyenne', 'mode': 'mode'}


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE : AGENT A2 PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════════

# DATA DICTIONNAIRE — Traçabilité des variables dérivées
# Exigence : ACPR-2022-P-01 §3.2
DATA_DICTIONNAIRE = {
    'log_cout_total_sinistres': {
        'source': 'cout_total_sinistres',
        'operation': 'log1p(max(x, 0))',
        'justification': (
            'Distribution log-normale des couts de sinistres. '
            'Ameliore calibration GLM Gamma. '
            'Ref. : Haberman & Renshaw (1996) ASTIN Bulletin.'
        ),
        'usage': 'GLM Gamma (cout moyen)',
    },
    'age_carre': {
        'source': 'age', 'operation': 'age ** 2',
        'justification': (
            'Effet U-shape de age sur sinistralite : '
            '<25 ans et >70 ans sinistralite elevee. '
            'Ref. : ACPR statistiques sinistralite RC Auto France (2022).'
        ),
        'usage': 'GLM Poisson RC Auto',
    },
    'risque_historique': {
        'source': ['bonus_malus', 'antecedents_sinistres_n1'],
        'operation': 'bonus_malus * (1 + antecedents_sinistres_n1)',
        'justification': 'Double signal de sinistralite passee.',
        'usage': 'GLM Poisson RC Auto',
    },
    'km_par_an_normalise': {
        'source': ['kilometrage_annuel', 'exposition'],
        'operation': 'kilometrage_annuel / max(exposition, 0.01)',
        'justification': 'Kilometrage annualise = exposition kilometrique reelle.',
        'usage': 'GLM Poisson RC Auto',
    },
    'jeune_conducteur': {
        'source': 'age', 'operation': '(age < 25).astype(int)',
        'justification': 'Sinistralite <25 ans : 2.5x moyenne. Ref. : ACPR (2022).',
        'usage': 'GLM Poisson RC Auto',
    },
    'log_exposition': {
        'source': 'exposition', 'operation': 'log(max(exposition, 1e-6))',
        'justification': (
            'Offset GLM Poisson. Annualise la frequence. '
            'Ref. : McCullagh & Nelder (1989) §6.3.'
        ),
        'usage': 'GLM Poisson (offset)',
    },
}


# La relation dérivée→source vit désormais dans core.derivations (SOURCE UNIQUE,
# partagée par le plan — colonnes_attendues() — et le moteur de mapping). A2 y
# DÉLÈGUE : fin du couplage à DATA_DICTIONNAIRE, qui n'en documentait que 3 des 9
# (la table core est complète). Effet de bord VOULU : valider_contre() nomme
# désormais AUSSI valeur_mobilier / annee_construction (mrh), pas seulement les 3
# dérivées auto documentées — le correctif du #4 était partiel, il est complété.
from core.derivations import sources_brutes as _sources_brutes

# ── TRAÇABILITÉ DES INTERACTIONS — désormais PILOTÉE PAR LE PLAN (Phase 2) ───
# Les entrées ci-dessus documentent les variables dérivées "simples" (statiques,
# calculées par _calculer_indicateurs_derives). Les variables d'interaction
# 'inter_{a}_{b}' n'étaient PAS documentées avant l'audit V4 (écart de
# traçabilité ACPR-2022-P-01 §3.2) ; elles l'étaient ensuite par une boucle sur
# le dict INTERACTIONS, codé en dur.
#
# INTERACTIONS ayant disparu, cette boucle de module aussi : les entrées sont
# générées À L'EXÉCUTION à partir de plan.interactions, dans run() (voir
# _dictionnaire_avec_interactions). La traçabilité reste donc synchrone PAR
# CONSTRUCTION avec ce qui crée réellement les colonnes — et elle couvre
# désormais TOUTE LoB déclarée (décennale, marchandises…), plus seulement les
# trois qui étaient codées en dur.


def _dictionnaire_avec_interactions(plan: "PlanTarifaire") -> Dict[str, Any]:
    """DATA_DICTIONNAIRE + une entrée par interaction DÉCLARÉE au plan.
    Source unique de la traçabilité ACPR-2022-P-01 §3.2 des colonnes dérivées."""
    dico = dict(DATA_DICTIONNAIRE)
    for _a, _b in plan.interactions:
        dico.setdefault(f"inter_{_a}_{_b}", {
            'source': [_a, _b],
            'operation': f"{_a} * {_b}",
            'justification': (
                f"Variable d'interaction DÉCLARÉE par le plan signé "
                f"'{plan.lob}'. Capture un effet non-additif entre '{_a}' et "
                f"'{_b}' que le GLM log-linéaire seul ne peut pas modéliser. "
                f"Produite par A2 si les deux colonnes source existent ; son "
                f"absence est rapportée dans 'colonnes_plan_manquantes'."
            ),
            'usage': f"GLM / ML / DL — plan '{plan.lob}'",
        })
    return dico


class AgentA2Preprocessing:
    """
    Agent A2 — Preprocessing & Feature Engineering.

    Transforme les données brutes validées par A1 en données
    prêtes pour la calibration des modèles actuariels (A3/A4/A5).

    AUTONOMIE NIVEAU 2 :
    L'agent choisit ses paramètres de façon autonome et justifie
    chaque décision. Il logue toutes ses transformations pour
    garantir la reproductibilité (exigence S2 / IFRS 17).

    EXEMPLE D'UTILISATION :
    ─────────────────────────
    # Après avoir exécuté l'agent A1 :
    result_a1 = agent_a1.run(branche='non_vie',
                              fichier='contrats_auto_70k.parquet')

    agent_a2 = AgentA2Preprocessing(
        models_path='/tmp/actuaria',
        audit_path ='/tmp/actuaria',
    )
    result_a2 = agent_a2.run(result_a1)

    df_pret   = result_a2['dataframe']     # Données prêtes pour GLM/ML
    rapport   = result_a2['rapport']       # Rapport des transformations
    params    = result_a2['parametres']    # Paramètres sauvegardés
    """

    def __init__(
        self,
        models_path: str = '/tmp/actuaria',
        audit_path:  str = '/tmp/actuaria',
        verbose:     bool = True
    ):
        """
        Initialise l'agent A2.

        Paramètres
        ──────────
        models_path : str
            Chemin de sauvegarde des paramètres de preprocessing.
            Les paramètres (médiane, mode, encodeurs) sont sauvegardés
            pour permettre la reproductibilité sur de nouvelles données.
            Exigence S2 : tout calcul actuariel doit être reproductible.

        audit_path : str
            Chemin des logs d'audit trail.

        verbose : bool
            Affiche les commentaires actuaire sénior si True.
        """
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.verbose     = verbose

        # Création des dossiers si inexistants
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)

        # Dictionnaire des paramètres appris
        # Contient toutes les valeurs calculées sur les données d'entraînement
        # pour pouvoir les réappliquer sur de nouvelles données
        self.parametres = {
            'medianes':      {},   # Médianes pour imputation numérique
            'modes':         {},   # Modes pour imputation catégorielle
            'winsor_bounds': {},   # Bornes Winsorisation
            'encodeurs':     {},   # Encodeurs label/one-hot
            'stats_expo':    {},   # Statistiques exposition
            'version':       '1.0',
            'timestamp':     None,
            'sous_branche':  None,
        }

        if self.verbose:
            logger.info("Agent A2 Preprocessing initialisé")

    # ══════════════════════════════════════════════════════════════════════════
    # MÉTHODE PRINCIPALE : run()
    # ══════════════════════════════════════════════════════════════════════════

    def run(
        self,
        result_a1: Dict[str, Any],
        cible_frequence: str = 'nb_sinistres',
        cible_cout:      str = 'cout_total_sinistres',
        plan: Optional["PlanTarifaire"] = None,   # Phase 2 : plan signé explicite
    ) -> Dict[str, Any]:
        """
        Pipeline complet de preprocessing.

        Paramètres
        ──────────
        result_a1 : dict
            Résultat de l'agent A1 (doit contenir 'dataframe' et 'branche').

        cible_frequence : str
            Nom de la colonne cible pour le modèle de fréquence (GLM Poisson).
            Par défaut : 'nb_sinistres'

        cible_cout : str
            Nom de la colonne cible pour le modèle de coût (GLM Gamma).
            Par défaut : 'cout_total_sinistres'

        Retourne
        ────────
        dict avec :
            'dataframe'   : DataFrame preprocessé prêt pour A3/A4
            'rapport'     : rapport des transformations effectuées
            'parametres'  : paramètres appris (pour reproductibilité)
            'statut_rag'  : 'VERT', 'AMBRE' ou 'ROUGE'
            'commentaire' : commentaire actuaire sénior
            'audit_id'    : identifiant audit trail
        """
        t_debut    = datetime.now()
        audit_id   = f"A2_{t_debut.strftime('%Y%m%d_%H%M%S')}"
        sous_branche = result_a1.get('branche', 'inconnue')

        logger.info(f"[{audit_id}] Agent A2 démarré | branche={sous_branche}")

        # Vérification que A1 a réussi
        if not result_a1.get('success', False):
            return self._erreur(
                "L'agent A1 a échoué. Corrigez les données avant de "
                "lancer A2.", audit_id
            )

        # Phase 2 : l'encodage et les interactions sont DÉCLARÉS par le plan
        # signé (VARS_CATEGORIELLES/INTERACTIONS supprimés). Plan absent →
        # erreur propre, JAMAIS de repli : un repli réintroduirait exactement le
        # décalage silencieux A2/A3 que ce refactor supprime.
        if plan is None:
            return self._erreur(
                "A2.run exige un plan (PlanTarifaire) : l'encodage (one-hot vs "
                "label, ordre des modalités), les transformations et les "
                "interactions sont dérivés du plan signé (Phase 2, "
                "VARS_CATEGORIELLES/INTERACTIONS supprimés). Fournissez "
                "plan=PlanTarifaire.depuis_yaml('plans/<lob>.yaml').", audit_id)

        df = result_a1['dataframe'].copy()
        self.parametres['sous_branche'] = sous_branche
        self.parametres['timestamp']    = t_debut.isoformat()

        rapport = {
            'etapes':          [],
            'nb_lignes_debut': len(df),
            'nb_cols_debut':   len(df.columns),
            'transformations': {},
            'features_creees': [],
            'features_supprimees': [],
        }

        try:
            # ── ÉTAPE 1 : IMPUTATION ──────────────────────────────────────────
            logger.info(f"[{audit_id}] Étape 1/6 : Imputation valeurs manquantes")
            df, stats_imput = self._imputer(df, sous_branche, plan)
            rapport['etapes'].append('imputation')
            rapport['transformations']['imputation'] = stats_imput

            # ── ÉTAPE 2 (ex-WINSORISATION) — DÉPLACÉE dans _appliquer_plan ────
            # La winsorisation est désormais pilotée par le PLAN et s'exécute
            # APRÈS le calcul des dérivées (comme dans fit/transform), donc à
            # l'étape 5. Elle ne peut pas rester ici : les dérivées n'existent
            # pas encore, et c'est exactement pour ça qu'elles n'étaient JAMAIS
            # écrêtées côté agent alors que le déclaratif les traitait.

            # ── ÉTAPE 3 : EXPOSITION ──────────────────────────────────────────
            logger.info(f"[{audit_id}] Étape 3/6 : Calcul/validation exposition")
            df, stats_expo = self._traiter_exposition(df, sous_branche)
            rapport['etapes'].append('exposition')
            rapport['transformations']['exposition'] = stats_expo

            # ── ÉTAPE 4 : CONTRAT DE DONNÉES — prime_pure (HORS plan) ─────────
            # prime_pure n'est PAS un facteur tarifaire : c'est une grandeur de
            # la famille cible, exclue des modèles par le garde-fou anti-fuite.
            # Elle reste produite par le pipeline (contrat V7 B2), pas par le plan.
            df = self._calculer_prime_pure(df)

            # ── ÉTAPE 5 : COLONNES DÉCLARÉES PAR LE PLAN ──────────────────────
            logger.info(f"[{audit_id}] Étape 5/6 : Encodage + features (plan "
                        f"'{plan.lob}')")
            df, stats_plan = self._appliquer_plan(df, plan)
            rapport['etapes'].append('plan')
            rapport['etapes'].append('winsorisation')
            rapport['transformations']['winsorisation'] = stats_plan['winsorisation']
            rapport['transformations']['encodage'] = stats_plan['encodage']
            rapport['features_creees'] = stats_plan['colonnes_produites']
            rapport['colonnes_plan_manquantes'] = stats_plan['manquantes']

            # ── ÉTAPE 6 : VALIDATION FINALE ───────────────────────────────────
            logger.info(f"[{audit_id}] Étape 6/6 : Validation finale")
            df, stats_valid = self._valider_sortie(
                df, sous_branche, cible_frequence, cible_cout
            )
            rapport['etapes'].append('validation')
            rapport['transformations']['validation'] = stats_valid

            # Mise à jour rapport
            rapport['nb_lignes_fin'] = len(df)
            rapport['nb_cols_fin']   = len(df.columns)
            rapport['nb_features_ajoutees'] = (
                len(df.columns) - rapport['nb_cols_debut']
            )

            # Trace d'audit. ⚠️ Ce n'est plus conditionne a un mode : le
            # mecanisme 'predict' a ete retire avec sa promesse (`a2/C17`).
            self._sauvegarder_parametres(sous_branche)

            # Commentaire actuaire sénior
            statut_rag  = self._calculer_statut_rag(rapport, df)
            commentaire = self._commenter_actuaire_senior(
                rapport, sous_branche, statut_rag,
                cible_frequence, cible_cout, df
            )

            # Audit trail
            self._sauvegarder_audit(audit_id, sous_branche, rapport,
                                     statut_rag, t_debut)

            if self.verbose:
                self._afficher_rapport_console(
                    audit_id, sous_branche, rapport,
                    statut_rag, commentaire
                )

            # ── Audit trail — traçabilité ACPR ────────────────────────────────
            # Traçabilité ACPR §3.2 : dérivées statiques + interactions du PLAN.
            _dico_a2 = _dictionnaire_avec_interactions(plan)

            _audit_trail_a2 = {
                'agent': 'A2_PREPROCESSING', 'version': '1.0', 'audit_id': audit_id,
                'timestamp': datetime.now().isoformat(), 'branche': sous_branche,
                'statut_rag': statut_rag,
                'nb_variables_derivees_tracees': len(_dico_a2),
                'plan_lob': plan.lob,
                'etapes': rapport.get('etapes', []),
            }

            _tmp_a2 = {
                'success': True, 'statut_rag': statut_rag, 'branche': sous_branche,
                'rapport': rapport, 'audit_id': audit_id, 'commentaire': commentaire,
                'data_dictionnaire': _dico_a2,
            }
            _excel_a2 = b''
            if TARIF_EXCEL_OK_A2:
                try:
                    _excel_a2 = export_excel_a2(_tmp_a2, audit_id)
                    if _excel_a2:
                        logger.info(f"[{audit_id}] Excel A2 : {len(_excel_a2):,} bytes")
                except Exception as e_xl:
                    logger.warning(f"Excel A2 échoué : {e_xl}")

            return {
                'success':           True,
                'dataframe':         df,
                'branche':           sous_branche,
                'statut_rag':        statut_rag,
                'rapport':           rapport,
                'parametres':        self.parametres,
                'commentaire':       commentaire,
                'audit_id':          audit_id,
                'erreur':            None,
                # ── RAPPORT EXPLICITE : colonnes du plan NON produites ────────
                # Visible dans le dict de retour, pas seulement en log ("ce qui
                # n'est que dans les logs n'existe pas"). A6 le relaie jusqu'aux
                # 3 livrables, comme rapport_qualite et alertes_modele.
                'colonnes_plan_manquantes': stats_plan['manquantes'],
                # Traçabilité des variables dérivées — ACPR-2022-P-01 §3.2
                'data_dictionnaire': _dico_a2,
                'excel_bytes':       _excel_a2,
                'word_bytes':        b'',
                'pdf_bytes':         b'',
                'audit_trail':       _audit_trail_a2,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), audit_id)

    # ══════════════════════════════════════════════════════════════════════════
    # fit / transform — LE PIVOT (étape 2 du plan d'exécution)
    # ══════════════════════════════════════════════════════════════════════════
    # `run()` fait tout en une passe : c'est ce qui rend le scoring impossible.
    # fit() apprend UNIQUEMENT sur le portefeuille d'apprentissage (modalités,
    # médianes d'imputation, bornes de winsorisation) ; transform() applique les
    # MÊMES paramètres — utilisable sur 1 contrat comme sur 1 million. Deux effets :
    #   1. transform sur un contrat neuf  → débloque tarifer() (INV-7) ;
    #   2. l'assert final EST INV-1        → le contrat A2→A3 se vérifie à chaque appel.
    #
    # Piège V9 payé cher : on ne RECALCULE JAMAIS les modalités dans transform.
    # Une modalité absente d'un contrat neuf → colonne one-hot à 0 ; une modalité
    # INCONNUE → on lève, on n'ignore pas (les échecs silencieux ont trop coûté).

    _WINSOR_Q = (0.01, 0.99)   # bornes de winsorisation des features continues

    def _calculer_indicateurs_derives(self, out: pd.DataFrame) -> pd.DataFrame:
        """Indicateurs auto DÉRIVÉS — calculés automatiquement à partir d'autres
        colonnes, avec les MÊMES formules et seuils que l'ancien
        A2._feature_engineering (25/70 ans, 3/10 ans, bonus_malus×(1+antécédents),
        km/exposition). Ce ne sont PAS des facteurs saisis par le client : le plan
        les déclare ensuite comme facteurs binaire/continu ordinaires, sans avoir à
        savoir COMMENT ils sont calculés — seulement qu'ils existent en sortie de
        transform(). Chaque calcul est GARDÉ par la présence de ses sources."""
        if "bonus_malus" in out.columns and "antecedents_sinistres_n1" in out.columns:
            out["risque_historique"] = (
                pd.to_numeric(out["bonus_malus"], errors="coerce")
                * (1 + pd.to_numeric(out["antecedents_sinistres_n1"], errors="coerce")))
        if "kilometrage_annuel" in out.columns and "exposition" in out.columns:
            out["km_par_an_normalise"] = (
                pd.to_numeric(out["kilometrage_annuel"], errors="coerce")
                / np.maximum(pd.to_numeric(out["exposition"], errors="coerce"), 0.01))
        if "age" in out.columns:
            _age = pd.to_numeric(out["age"], errors="coerce")
            out["jeune_conducteur"] = (_age < 25).astype(int)
            out["senior_conducteur"] = (_age > 70).astype(int)
        if "age_vehicule" in out.columns:
            _av = pd.to_numeric(out["age_vehicule"], errors="coerce")
            out["vehicule_recent"] = (_av < 3).astype(int)
            out["vehicule_ancien"] = (_av > 10).astype(int)
        # ── MRH (mêmes formules que _feature_engineering) ────────────────────
        if "valeur_mobilier" in out.columns and "surface_m2" in out.columns:
            out["valeur_par_m2"] = (
                pd.to_numeric(out["valeur_mobilier"], errors="coerce")
                / np.maximum(pd.to_numeric(out["surface_m2"], errors="coerce"), 1))
        if "annee_construction" in out.columns:
            # ⚠ CORRECTIF DE BUG (trouvé pendant la migration MRH) : l'ancien A2
            # codait l'année de référence EN DUR (2024) — un bug de CALENDRIER qui
            # se dégradait d'un an chaque année (age_logement faux de +1 an à
            # chaque nouvel an sur les mêmes données). On utilise désormais
            # l'année d'EXÉCUTION : age_logement est toujours à jour, jamais périmé.
            _annee_ref = datetime.now().year
            out["age_logement"] = (_annee_ref
                                   - pd.to_numeric(out["annee_construction"], errors="coerce"))
            out["logement_ancien"] = (out["age_logement"] > 50).astype(int)
        return out

    def _calculer_prime_pure(self, df: pd.DataFrame) -> pd.DataFrame:
        """CONTRAT DE DONNÉES — prime_pure (audit V7 BLOQUANT #2). HORS PLAN.

        prime_pure n'est PAS un facteur tarifaire : c'est une grandeur de la
        FAMILLE CIBLE (coût / exposition), que le garde-fou anti-fuite exclut des
        matrices X. Elle n'a donc rien à faire dans un plan — mais A3/A4/A6 la
        référencent comme cible par défaut. AVANT le correctif V7, elle était
        attendue mais JAMAIS produite : en invocation par défaut d'A6
        (col_cible='prime_pure'), le walk-forward se désactivait SILENCIEUSEMENT
        (backtest['disponible']=False, sans erreur) et le statut RAG pouvait
        rester VERT sans qu'aucune validation temporelle n'ait tourné.

        Même formule qu'à l'origine : prime pure = coût total / exposition.
        (Bloc extrait tel quel de l'ancien _feature_engineering, supprimé en
        Phase 2 — le calcul est inchangé, seul son point d'appel a bougé.)
        """
        if ('prime_pure' not in df.columns
                and 'cout_total_sinistres' in df.columns
                and 'exposition' in df.columns):
            _expo_safe = np.maximum(df['exposition'], 1e-6)
            df['prime_pure'] = df['cout_total_sinistres'] / _expo_safe
            logger.info(
                "'prime_pure' calculée automatiquement "
                "(cout_total_sinistres / exposition) — absente des données "
                "brutes en entrée. Réf. : audit V7 BLOQUANT #2."
            )
        return df

    def _appliquer_plan(
        self, df: pd.DataFrame, plan: "PlanTarifaire"
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Chemin AGENT : produit les colonnes DÉCLARÉES par le plan, pour les
        facteurs dont la colonne source est PRÉSENTE. Tout ce qui n'a pas pu être
        produit est RAPPORTÉ — jamais tu.

        Réutilise _appliquer_facteur() : le chemin agent et le chemin déclaratif
        (fit/transform) partagent LITTÉRALEMENT la même autorité d'encodage
        (one-hot vs label, ordre des modalités, transformations). Fin de la
        troisième implémentation, et fin du décalage silencieux A2/A3.

        DIFFÉRENCE ASSUMÉE avec transform() : celui-ci EXIGE un fichier complet
        (fit → valider_contre lève) et garantit INV-1. run() sert aussi des
        portefeuilles partiels (diagnostic, tests de garde-fou) : il rapporte
        l'écart au lieu de refuser. DÉCIDER de tarifer malgré un plan incomplet
        n'est pas le métier du préprocessing — c'est celui d'A3/A6.
        """
        df = self._calculer_indicateurs_derives(df)

        # ── WINSORISATION PILOTÉE PAR LE PLAN ────────────────────────────────
        # MÊME _WINSOR_Q que fit/transform : une seule définition des bornes,
        # pour les deux chemins. Et APRÈS les dérivées, comme transform.
        #
        # ⚠ Remplace SEUILS_WINSOR, la DERNIÈRE liste codée en dur du pipeline
        # (valeur_venale/kilometrage_annuel = auto ; ca_annuel_eur = rcpro).
        # L'écart qu'elle laissait était béant : sur auto, fit/transform écrêtait
        # 9 facteurs continus, A2.run UN SEUL (valeur_venale) — plus
        # kilometrage_annuel, qui n'est même pas un facteur du plan (seul son
        # dérivé km_par_an_normalise l'est). Et les dérivées (risque_historique,
        # km_par_an_normalise) n'étaient JAMAIS écrêtées côté agent, puisque
        # l'ancienne étape 2 s'exécutait avant leur calcul. Le plan décide
        # désormais, des deux côtés, pour toute LoB — y compris celles qu'aucune
        # liste ne connaissait.
        winsorisees: Dict[str, Any] = {}
        q_inf, q_sup = self._WINSOR_Q
        for f in plan.facteurs:
            if f.type != 'continu' or f.nom not in df.columns:
                continue
            serie = pd.to_numeric(df[f.nom], errors='coerce')
            lo, hi = float(serie.quantile(q_inf)), float(serie.quantile(q_sup))
            n_ecretees = int(((serie < lo) | (serie > hi)).sum())
            if n_ecretees:
                df[f.nom] = serie.clip(lower=lo, upper=hi)
                winsorisees[f.nom] = {
                    'borne_inf': round(lo, 4), 'borne_sup': round(hi, 4),
                    'n_valeurs_ecretees': n_ecretees,
                }
        if winsorisees:
            logger.info(f"Winsorisation (plan '{plan.lob}') : "
                        f"{len(winsorisees)} facteur(s) continu(s) écrêté(s) "
                        f"aux quantiles {q_inf}/{q_sup}")

        # Codes label : ORDRE DU PLAN (autorité), comme fit(). Surtout PAS l'ordre
        # alphabétique de sklearn : il avait inversé le signal zone/milieu (254c959).
        self._codes_label = {}
        for f in plan.facteurs:
            if (f.nom in df.columns and f.type not in ("continu", "binaire")
                    and f.encodage == "label"):
                mods = (list(f.modalites) if f.modalites
                        else sorted(df[f.nom].dropna().astype(str).unique()))
                self._codes_label[f.nom] = {str(m): i for i, m in enumerate(mods)}

        facteurs_absents: List[str] = []
        encodage: Dict[str, str] = {}
        for f in plan.facteurs:
            if f.nom not in df.columns:
                facteurs_absents.append(f.nom)
                continue
            self._appliquer_facteur(df, f)   # modalité INCONNUE → lève (piège V9)
            if f.type not in ("continu", "binaire"):
                encodage[f.nom] = f.encodage

        # Interactions DÉCLARÉES : inter_{a}_{b} = a * b (mêmes noms que transform)
        for a, b in plan.interactions:
            if a in df.columns and b in df.columns:
                df[f"inter_{a}_{b}"] = (pd.to_numeric(df[a], errors="coerce")
                                        * pd.to_numeric(df[b], errors="coerce")).astype(float)

        attendues     = list(plan.colonnes_produites())
        produites     = [c for c in attendues if c in df.columns]
        non_produites = [c for c in attendues if c not in df.columns]
        if non_produites:
            logger.warning(
                "[PLAN '%s'] %d colonne(s) déclarée(s) NON produite(s) : %s — "
                "facteur(s) source absent(s) du fichier client : %s. Les modèles "
                "tourneront SANS ces facteurs. Écart remonté dans "
                "result['colonnes_plan_manquantes'], jusqu'aux livrables.",
                plan.lob, len(non_produites), non_produites, facteurs_absents)
        return df, {
            'encodage':           encodage,
            'winsorisation':      winsorisees,
            'colonnes_produites': produites,
            'manquantes': {
                'plan':                  plan.lob,
                'facteurs_absents':      facteurs_absents,
                'colonnes_non_produites': non_produites,
            },
        }

    def fit(self, df: pd.DataFrame, plan: "PlanTarifaire") -> "AgentA2Preprocessing":
        """Apprend les paramètres de preprocessing SUR CE PORTEFEUILLE, à partir
        du plan signé. Fige : modalités, médianes d'imputation, bornes de
        winsorisation, modes catégoriels. Retourne self (chaînable)."""
        df = self._calculer_indicateurs_derives(df.copy())   # dérivées AVANT validation
        manquantes = plan.valider_contre(df.columns)
        if manquantes:
            # Nommer la SOURCE BRUTE, pas la dérivée : le client fournit
            # kilometrage_annuel, pas km_par_an_normalise (qu'A2 calcule). Sans ça,
            # le message désigne une colonne que le client ne peut pas produire.
            sources = [s for s in _sources_brutes(manquantes) if s not in df.columns]
            detail = ("" if sources == list(manquantes)
                      else f" (dérivée(s) non calculable(s) : {list(manquantes)})")
            raise ValueError(
                f"Fichier client incomplet pour le plan '{plan.lob}' : source(s) "
                f"manquante(s) {sources}.{detail}")

        self._plan = plan
        self._medianes: Dict[str, float] = {}
        self._bornes:   Dict[str, Tuple[float, float]] = {}
        self._modes:    Dict[str, Any] = {}
        self._codes_label: Dict[str, Dict[str, int]] = {}

        for f in plan.facteurs:
            col = f.nom
            if f.type in ("continu", "binaire"):
                serie = pd.to_numeric(df[col], errors="coerce")
                self._medianes[col] = float(serie.median())
                if f.type == "continu":
                    q_inf, q_sup = self._WINSOR_Q
                    self._bornes[col] = (float(serie.quantile(q_inf)),
                                         float(serie.quantile(q_sup)))
            else:  # catégoriel (one_hot ou label)
                serie = df[col].astype("object")
                mode = serie.mode()
                self._modes[col] = mode.iloc[0] if len(mode) else None
                if f.encodage == "label":
                    # Mapping modalité → code. Déclaré dans le plan → ordre du
                    # plan (déterministe, opposable) ; sinon appris (unique trié).
                    modalites = (list(f.modalites) if f.modalites
                                 else sorted(serie.dropna().astype(str).unique()))
                    self._codes_label[col] = {str(m): i for i, m in enumerate(modalites)}
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applique les MÊMES paramètres appris par fit(). Produit EXACTEMENT
        plan.colonnes_produites() — ou lève. L'assert final EST INV-1."""
        if getattr(self, "_plan", None) is None:
            raise RuntimeError("transform() appelé avant fit(). Appelez d'abord "
                               "fit(df_apprentissage, plan).")
        plan = self._plan
        out = df.copy()
        self._calculer_indicateurs_derives(out)   # dérivées d'abord (comme dans fit)

        # ── Pré-passe : imputation + winsorisation (paramètres FIGÉS par fit) ────
        for f in plan.facteurs:
            col = f.nom
            if col not in out.columns:
                continue
            if f.type in ("continu", "binaire"):
                serie = pd.to_numeric(out[col], errors="coerce")
                if col in self._medianes:
                    serie = serie.fillna(self._medianes[col])
                if f.type == "continu" and col in self._bornes:
                    lo, hi = self._bornes[col]
                    serie = serie.clip(lower=lo, upper=hi)
                out[col] = serie.astype(float)
            else:
                if self._modes.get(col) is not None:
                    out[col] = out[col].astype("object").fillna(self._modes[col])

        # ── Production des colonnes déclarées, facteur par facteur ──────────────
        for f in plan.facteurs:
            self._appliquer_facteur(out, f)

        # ── Interactions : inter_{a}_{b} = a * b (a, b = noms sources) ──────────
        for a, b in plan.interactions:
            for c in (a, b):
                if c not in out.columns:
                    raise ValueError(
                        f"Interaction ({a}×{b}) : colonne source '{c}' absente.")
            out[f"inter_{a}_{b}"] = (pd.to_numeric(out[a], errors="coerce")
                                     * pd.to_numeric(out[b], errors="coerce")).astype(float)

        # ── INV-1 : on produit EXACTEMENT ce que le plan annonce ────────────────
        attendues = set(plan.colonnes_produites())
        manquantes = attendues - set(out.columns)
        assert not manquantes, (
            f"INV-1 rompu : transform n'a pas produit {sorted(manquantes)}. "
            f"Le contrat A2→A3 est brisé.")
        return out

    def _appliquer_facteur(self, out: pd.DataFrame, f: "Facteur") -> None:
        """Produit, dans `out`, les colonnes que `f.colonnes_produites()` annonce.
        Le nom de chaque colonne vient du MÊME _slug / _SUFFIXE_TRANSFO que le
        plan — le contrat A2→A3 est donc littéralement la même fonction."""
        col = f.nom
        if f.type == "binaire":
            out[col] = pd.to_numeric(out[col], errors="coerce").astype(float)
            self._verifier_modalites_binaires(f, out[col])

        elif f.type == "continu":
            # La colonne de base existe déjà (imputée/winsorisée). On n'ajoute que
            # l'éventuelle transformée déclarée.
            if f.transformation:
                col_t = _SUFFIXE_TRANSFO[f.transformation].format(col)
                out[col_t] = self._transformer(out[col], f.transformation)

        elif f.encodage == "label":
            codes = self._codes_label.get(col)
            if codes is None:   # fit n'a pas vu ce facteur (df incohérent)
                raise RuntimeError(f"Label '{col}' non appris par fit().")
            vals = out[col].astype("object").astype(str)
            self._verifier_modalites_connues(f, vals, set(codes.keys()))
            out[f"{col}_enc"] = vals.map(codes).astype(float)

        elif f.encodage == "one_hot":
            ref = f.reference or f.modalites[0]
            declarees = {str(m) for m in f.modalites}
            vals = out[col].astype("object").astype(str)
            self._verifier_modalites_connues(f, vals, declarees)
            for m in f.modalites:
                if m == ref:          # modalité de référence : pas de colonne
                    continue
                out[f"{col}_{_slug(m)}"] = (vals == str(m)).astype(float)

    @staticmethod
    def _transformer(serie: pd.Series, transformation: str) -> pd.Series:
        x = pd.to_numeric(serie, errors="coerce")
        if transformation == "log":
            return np.log1p(x.clip(lower=0)).astype(float)
        if transformation == "carre":
            return (x ** 2).astype(float)
        if transformation == "racine":
            return np.sqrt(x.clip(lower=0)).astype(float)
        raise ValueError(f"Transformation inconnue : '{transformation}'.")

    @staticmethod
    def _verifier_modalites_connues(f: "Facteur", vals: pd.Series,
                                    declarees: set) -> None:
        """Piège V9 : une modalité INCONNUE → lever, ne pas l'ignorer. Une
        modalité déclarée mais absente de ce lot → simple colonne à 0 (permis)."""
        inconnues = set(vals.dropna().unique()) - declarees
        if inconnues:
            raise ValueError(
                f"Facteur '{f.nom}' : modalité(s) INCONNUE(S) {sorted(inconnues)} "
                f"— non déclarée(s) dans le plan (modalités figées : "
                f"{sorted(declarees)}). On lève plutôt que de produire une colonne "
                f"one-hot/label silencieusement fausse (piège V9).")

    @staticmethod
    def _verifier_modalites_binaires(f: "Facteur", vals: pd.Series) -> None:
        """Le pendant de `_verifier_modalites_connues`, pour le type `binaire`.

        ⚠️⚠️ L'ASYMÉTRIE ÉTAIT LE DÉFAUT (`a2/C8`). Un facteur `label` dont une
        modalité est inconnue fait LEVER ; un facteur `binaire` ne passait par
        AUCUN contrôle. Mesuré : une colonne 0/1 imputée par la moyenne sortait
        en `[0.0, 0.8152, 1.0]` — 40 lignes portant une valeur qui n'est pas une
        modalité — et le GLM recevait une variable dite binaire dont le
        coefficient ne contraste plus deux états.

        ⚠️ Les modalités d'un binaire sont **implicites {0, 1}**, et c'est le
        plan qui l'impose : un facteur binaire ne porte AUCUN encodage
        (`plan_tarifaire`, « un facteur binaire ne s'encode pas ») et produit sa
        seule colonne telle quelle. Il n'y a donc pas de modalités déclarées à
        lire — il y a une définition à faire respecter.

        On lève, comme pour `label` : produire une colonne silencieusement
        fausse est pire que s'arrêter.
        """
        etrangeres = sorted(set(vals.dropna().unique()) - _MODALITES_BINAIRES)
        if etrangeres:
            # ⚠️ `float(...)` : sans lui le message publie « np.float64(2.0) ».
            # Il est lu par un actuaire, pas par un interpreteur.
            lisibles = [float(v) for v in etrangeres]
            raise ValueError(
                f"Facteur '{f.nom}' declare 'binaire' : valeur(s) HORS "
                f"MODALITE {lisibles} — un binaire ne prend que "
                f"{sorted(_MODALITES_BINAIRES)}. On leve plutot que de livrer "
                f"aux modeles une variable dite binaire qui n'en est plus une "
                f"(son coefficient ne contrasterait plus deux etats). Cause la "
                f"plus frequente : une imputation par la moyenne au lieu du "
                f"mode.")

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 1 : IMPUTATION
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _categorie_imputation(col: str, serie: pd.Series, cols_cat,
                              binaires: set, mots_asymetriques: list):
        """La categorie de `STRATEGIES_IMPUTATION` a laquelle cette colonne
        appartient, ou None si aucune (type non gere -> repli).

        ⚠️⚠️ L'ORDRE N'EST PAS LIBRE : `binaire` SE TESTE EN PREMIER. Un binaire
        est numerique ; teste apres le dtype, il tombait dans
        `numerique_symetrique` et recevait la MOYENNE. C'est exactement par la
        que `a2/C8` passait.
        ⚠️ Et c'est le PLAN qui dit ce qui est binaire, pas la forme des donnees
        : le plan signe est l'autorite, deviner sur les valeurs observees ferait
        dependre une strategie d'imputation du hasard d'un lot.
        """
        if col in binaires:
            return 'binaire'
        if col in cols_cat:
            return 'categorielle'
        if serie.dtype in ['int64', 'float64', 'int32', 'float32']:
            return ('numerique_asymetrique'
                    if any(mot in col.lower() for mot in mots_asymetriques)
                    else 'numerique_symetrique')
        return None

    def _imputer(
        self,
        df: pd.DataFrame,
        sous_branche: str,
        plan: "PlanTarifaire"
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Imputation des valeurs manquantes par type de variable.

        ⚠️⚠️ LES STRATEGIES SONT LUES DANS `STRATEGIES_IMPUTATION`, PLUS
        RECOPIEES ICI. C'etait `a2/C7` + `a2/C8`, un seul defaut vu des deux
        cotes : la table n'etait lue par personne (mesure par AST -- une seule
        occurrence dans tout le depot, sa propre definition) et cette fonction
        en reecrivait TROIS entrees en dur. La quatrieme, `binaire -> mode`,
        n'existait donc NULLE PART : une colonne 0/1 recevait la MOYENNE et
        sortait avec une valeur qui n'est pas une modalite.

        STRATEGIE ACTUARIELLE -- la justification de chaque entree de la table :

        Variables numeriques asymetriques (couts, primes) -> MEDIANE
        Les distributions de couts sont fortement asymetriques a droite
        (quelques sinistres tres couteux). La mediane est robuste aux outliers ;
        imputer par la moyenne introduirait un biais vers le haut.

        Variables numeriques symetriques (age, duree) -> MOYENNE
        Les distributions d'age sont quasi-normales : la moyenne y est un
        estimateur efficace.

        Variables categorielles -> MODE
        On conserve la structure de distribution sans creer de categorie
        artificielle.

        Variables binaires (0/1) -> MODE
        On conserve la valeur majoritaire. ⚠️ Et surtout : le mode EST une
        modalite, la moyenne ne l'est pas. `_verifier_modalites_binaires`
        refuse desormais le second cas.

        ⚠️⚠️ CE QUI A ETE RETIRE ICI, ET POURQUOI (`a2/C17`) : cette docstring
        promettait que les parametres calcules en 'train' etaient REUTILISES en
        'predict', « ce qui evite la fuite de donnees ». Mesure : une colonne
        saine au train ne laissait aucun parametre, et le repli
        `.get(col, df[col].mean())` recalculait sur les donnees de PREDICT --
        la fuite exacte que la phrase disait eviter. Le mecanisme etait mort
        (aucun appelant en 'predict', `charger_parametres` sans appelant) : il a
        ete retire AVEC sa promesse, plutot que repare. *Une garantie qu'on ne
        tient pas vaut moins que pas de garantie du tout.*

        `self.parametres` reste alimente : c'est une TRACE d'audit, sauvegardee
        en JSON. Ce n'est plus une promesse de reproductibilite.
        """
        stats = {
            'nb_cellules_avant': int(df.isnull().sum().sum()),
            'colonnes_imputees': {},
        }

        # Identification des colonnes avec valeurs manquantes
        cols_avec_na = df.columns[df.isnull().any()].tolist()

        if not cols_avec_na:
            logger.info("Aucune valeur manquante — imputation non nécessaire")
            stats['nb_cellules_apres'] = 0
            return df, stats

        # Variables numériques asymétriques (coûts, primes, capitaux)
        # Identifiées par leur nom
        mots_asymetriques = [
            'cout', 'prime', 'capital', 'valeur', 'montant',
            'encours', 'charge', 'ij', 'rente', 'ca_annuel',
            'provision', 'engagement'
        ]

        # Variables catégorielles
        cols_cat = df.select_dtypes(include=['object', 'category']).columns

        # ⚠️ Le PLAN dit ce qui est binaire (cf. `_categorie_imputation`).
        binaires = {f.nom for f in plan.facteurs if f.type == 'binaire'}

        for col in cols_avec_na:
            nb_na  = int(df[col].isnull().sum())
            pct_na = nb_na / len(df) * 100
            valeur = None

            categorie = self._categorie_imputation(
                col, df[col], cols_cat, binaires, mots_asymetriques)

            if categorie is None:
                # Type non gere par la table -> repli mediane si possible.
                try:
                    valeur = df[col].median()
                    df[col] = df[col].fillna(valeur)
                    methode = 'mediane_fallback'
                except Exception:
                    methode = 'non_imputee'
            else:
                strategie = STRATEGIES_IMPUTATION[categorie]
                valeur    = _CALCUL_IMPUTATION[strategie](df[col])

                # Comportement conserve : une categorielle sans mode calculable
                # recoit une modalite explicite plutot que de rester vide.
                if valeur is None and categorie == 'categorielle':
                    valeur = 'INCONNU'

                if valeur is None or (not isinstance(valeur, str)
                                      and pd.isna(valeur)):
                    methode = 'non_imputee'
                else:
                    df[col] = df[col].fillna(valeur)
                    methode = _LIBELLE_IMPUTATION[strategie]
                    # ⚠️ `medianes` heberge aussi les MOYENNES : c'est `a2/C9`,
                    # classe rang 5, deliberement NON corrige ici. Renommer la
                    # cle change le format d'un JSON persiste.
                    cle = 'modes' if strategie == 'mode' else 'medianes'
                    self.parametres[cle][col] = valeur

            stats['colonnes_imputees'][col] = {
                'nb_na':   nb_na,
                'pct_na':  round(pct_na, 2),
                'methode': methode,
                'valeur':  float(valeur) if isinstance(valeur, (int, float, np.number)) else str(valeur),
            }

        stats['nb_cellules_apres'] = int(df.isnull().sum().sum())
        logger.info(
            f"Imputation : {stats['nb_cellules_avant']} → "
            f"{stats['nb_cellules_apres']} valeurs manquantes"
        )

        return df, stats

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 2 : WINSORISATION
    # ══════════════════════════════════════════════════════════════════════════

    # (_winsoriser SUPPRIMÉE avec SEUILS_WINSOR — Phase 2, dernière liste codée.
    #  La winsorisation est desormais PILOTÉE PAR LE PLAN, dans _appliquer_plan,
    #  avec le MÊME _WINSOR_Q que fit/transform et APRÈS le calcul des dérivées.)

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 3 : EXPOSITION
    # ══════════════════════════════════════════════════════════════════════════

    def _traiter_exposition(
        self,
        df: pd.DataFrame,
        sous_branche: str
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Traitement et validation de la variable exposition.

        RÔLE ACTUARIEL DE L'EXPOSITION :
        ──────────────────────────────────
        L'exposition est LA variable centrale du GLM Poisson en Non-Vie.
        Elle représente la fraction d'année pendant laquelle le contrat
        était en vigueur.

        Dans le GLM Poisson : E[nb_sinistres] = λ × exposition
        L'exposition entre dans le modèle comme OFFSET :
        log(E[Y]) = log(exposition) + X'β

        Sans exposition, on modélise le nombre brut de sinistres
        → biais systématique pour les contrats partiels.
        Avec exposition, on modélise le TAUX de sinistres par an
        → estimation non biaisée de λ.

        RÈGLES DE VALIDATION :
        • exposition ∈ ]0, 1] — valeur réglementaire
        • exposition = 0 → contrat de durée nulle → à exclure
        • exposition > 1 → impossible pour un contrat annuel → correction

        Pour la branche Vie, l'exposition est gérée différemment :
        on utilise la durée résiduelle du contrat en années.
        """
        stats = {
            'col_exposition_trouvee': False,
            'valeurs_corrigees':      0,
            'lignes_exclues':         0,
        }

        # Recherche de la colonne exposition
        col_expo = None
        for col in df.columns:
            if 'exposition' in col.lower():
                col_expo = col
                break

        if col_expo is None:
            # Pas de colonne exposition trouvée
            # On crée une exposition unitaire (= 1 an pour tous)
            # et on logue un avertissement
            logger.warning(
                "Colonne 'exposition' introuvable. "
                "Exposition unitaire (=1) créée pour tous les contrats. "
                "Vérifiez vos données — l'exposition est indispensable "
                "pour le GLM Poisson."
            )
            df['exposition'] = 1.0
            col_expo = 'exposition'
            stats['exposition_creee'] = True
        else:
            stats['col_exposition_trouvee'] = True

        # Correction des valeurs aberrantes
        # exposition <= 0 : impossible — on remplace par la médiane
        nb_negatifs = (df[col_expo] <= 0).sum()
        if nb_negatifs > 0:
            mediane_expo = df[col_expo][df[col_expo] > 0].median()
            df.loc[df[col_expo] <= 0, col_expo] = mediane_expo
            stats['valeurs_corrigees'] += int(nb_negatifs)
            logger.warning(
                f"{nb_negatifs} valeurs d'exposition ≤ 0 remplacées "
                f"par la médiane ({mediane_expo:.4f})"
            )

        # exposition > 1 : contrat de plus d'un an
        # On plafonne à 1.0 (exposition maximale pour contrat annuel)
        nb_sup1 = (df[col_expo] > 1.0).sum()
        if nb_sup1 > 0:
            df.loc[df[col_expo] > 1.0, col_expo] = 1.0
            stats['valeurs_corrigees'] += int(nb_sup1)
            logger.warning(
                f"{nb_sup1} valeurs d'exposition > 1 plafonnées à 1.0"
            )

        # Calcul du log de l'exposition (offset pour GLM Poisson)
        # log(exposition) sera utilisé directement comme offset dans statsmodels
        df['log_exposition'] = np.log(np.maximum(df[col_expo], 1e-6))

        stats['exposition_min']    = round(float(df[col_expo].min()), 4)
        stats['exposition_max']    = round(float(df[col_expo].max()), 4)
        stats['exposition_median'] = round(float(df[col_expo].median()), 4)
        stats['exposition_mean']   = round(float(df[col_expo].mean()), 4)

        self.parametres['stats_expo'] = stats

        logger.info(
            f"Exposition : min={stats['exposition_min']} · "
            f"médiane={stats['exposition_median']} · "
            f"max={stats['exposition_max']}"
        )

        return df, stats

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPES 4-5 (ex-ENCODAGE / FEATURE ENGINEERING) — SUPPRIMÉES EN PHASE 2
    # ══════════════════════════════════════════════════════════════════════════
    # _encoder(), _feature_engineering(), _modalites_label_plan() et
    # _appliquer_label() sont SUPPRIMÉS : ils formaient la TROISIÈME
    # implémentation de l'encodage, et la dernière à décider du one-hot/label
    # depuis une liste codée en dur (VARS_CATEGORIELLES / INTERACTIONS).
    # run() appelle désormais _calculer_prime_pure() (contrat V7 B2, hors plan)
    # puis _appliquer_plan(), qui réutilise _appliquer_facteur() — la MÊME
    # autorité d'encodage que le chemin déclaratif fit/transform.
    #
    # Ce qui disparaît avec eux, sans regret :
    #   - le repli d'encodage LABEL AUTOMATIQUE des colonnes 'object' non
    #     configurées, qui recréait 'sexe_enc' en contournant le filtre genre ;
    #   - 'age_x_bonus_malus', doublon PARFAIT (corr +1,000) de l'interaction
    #     déclarée 'inter_age_bonus_malus', prouvé sans signal out-of-sample
    #     lors de l'alignement A4 ;
    #   - les variantes de nommage '{a}_x_{b}' des interactions.
    # prime_pure est PRÉSERVÉE (contrat de données V7 B2) : _calculer_prime_pure().

    # ══════════════════════════════════════════════════════════════════════════
    # ÉTAPE 6 : VALIDATION FINALE
    # ══════════════════════════════════════════════════════════════════════════

    def _valider_sortie(
        self,
        df: pd.DataFrame,
        sous_branche: str,
        cible_freq: str,
        cible_cout: str
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Validation finale du DataFrame preprocessé.

        Vérifie que :
        1. Il n'y a plus de valeurs manquantes dans les colonnes clés
        2. La variable cible (nb_sinistres) est bien non-négative
        3. L'exposition est bien dans ]0, 1]
        4. Le DataFrame est prêt pour les agents A3/A4/A5

        Supprime également les colonnes non utilisables par les modèles :
        - Identifiants (id_contrat, id_assure)
        - Dates brutes (date_souscription)
        - Colonnes object non encodées
        """
        stats = {
            'colonnes_supprimees': [],
            'nan_restants':        0,
            'pret_pour_glm':       False,
            'pret_pour_ml':        False,
        }

        # Colonnes à supprimer pour la modélisation
        # (conservées dans le DataFrame original pour le rapport)
        cols_id = [
            c for c in df.columns
            if any(mot in c.lower() for mot in [
                'id_contrat', 'id_assure', 'id_salarie',
                'id_beneficiaire', 'id_adherent',
            ])
        ]

        cols_date_brute = [
            c for c in df.columns
            if df[c].dtype == 'datetime64[ns]' or
               (df[c].dtype == 'object' and
                any(mot in c.lower() for mot in ['date_', 'annee_sous']))
        ]

        # On ne supprime pas — on crée un DataFrame de modélisation séparé
        # Le DataFrame complet reste disponible pour le rapport
        cols_a_exclure = set(cols_id + cols_date_brute)

        # Colonnes object restantes non encodées (à exclure du modèle)
        # ⚠️ UNE COLONNE BRUTE CONSERVÉE À CÔTÉ DE SES ENCODAGES N'EST PAS UNE
        # COLONNE NON ENCODÉE. A2 encode les facteurs catégoriels en AJOUTANT
        # `<nom>_<modalite>` (ou `<nom>_enc`) et en CONSERVANT la colonne
        # source — c'est voulu : le DataFrame complet reste disponible pour le
        # rapport. `_valider_sortie` comptait pourtant chaque source comme non
        # encodée. Conséquence mesurée sur les VINGT plans du dépôt, données
        # complètes et propres : le nombre de « colonnes non encodées »
        # signalées valait exactement le nombre de facteurs catégoriels, et
        # **VERT était atteint par 0 plan sur 20** — le statut VERT était
        # inatteignable. Le critère est désormais une propriété de la SORTIE :
        # une source est non encodée si AUCUNE colonne `<nom>_*` n'existe.
        cols_sortie = set(df.columns)
        cols_object_restantes = [
            c for c in df.select_dtypes(include=['object']).columns
            if c not in cols_a_exclure
            and not any(o.startswith(c + '_') for o in cols_sortie)
        ]

        stats['colonnes_non_encodees'] = cols_object_restantes
        stats['colonnes_id']           = cols_id

        # Vérification des NaN restants
        nan_restants = int(df.isnull().sum().sum())
        stats['nan_restants'] = nan_restants

        if nan_restants > 0:
            logger.warning(
                f"{nan_restants} valeurs manquantes restantes "
                "après imputation — vérification nécessaire"
            )

        # Vérification cible fréquence
        if cible_freq in df.columns:
            nb_negatifs = (df[cible_freq] < 0).sum()
            stats['pret_pour_glm'] = (nb_negatifs == 0)
        else:
            stats['pret_pour_glm'] = False
            logger.warning(
                f"Variable cible '{cible_freq}' introuvable. "
                "L'agent A3 (GLM Poisson) ne pourra pas calibrer "
                "le modèle de fréquence."
            )

        # Vérification exposition
        if 'exposition' in df.columns:
            expo_ok = ((df['exposition'] > 0) & (df['exposition'] <= 1)).all()
            stats['exposition_valide'] = bool(expo_ok)
        else:
            stats['exposition_valide'] = False

        # Liste des colonnes numériques disponibles pour les modèles
        cols_num = df.select_dtypes(
            include=['int64', 'float64', 'int32', 'float32']
        ).columns.tolist()
        stats['nb_features_numeriques'] = len(cols_num)
        stats['pret_pour_ml']           = len(cols_num) >= 5

        return df, stats

    # ══════════════════════════════════════════════════════════════════════════
    # VERSIONING & AUDIT
    # ══════════════════════════════════════════════════════════════════════════

    def _sauvegarder_parametres(self, sous_branche: str) -> None:
        """
        Sauvegarde les paramètres de preprocessing sur Drive.

        Ces paramètres permettent de :
        1. Reproduire exactement le même preprocessing sur de nouvelles données
        2. Répondre à un auditeur S2 sur les hypothèses utilisées
        3. Détecter une dérive des données (data drift) au fil du temps

        Format : JSON pour lisibilité humaine
        """
        nom_fichier = f"params_a2_{sous_branche}.json"
        chemin      = self.models_path / nom_fichier

        try:
            # Conversion des types numpy en types Python natifs
            params_serialisables = self._serialiser_params(self.parametres)

            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(params_serialisables, f, indent=2,
                          ensure_ascii=False, default=str)

            logger.info(f"Paramètres A2 sauvegardés : {chemin}")

        except Exception as e:
            logger.warning(f"Impossible de sauvegarder les paramètres : {e}")

    def _serialiser_params(self, obj: Any) -> Any:
        """Convertit les types numpy en types Python pour la sérialisation JSON."""
        if isinstance(obj, dict):
            return {k: self._serialiser_params(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialiser_params(i) for i in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj

    def _sauvegarder_audit(
        self,
        audit_id: str,
        sous_branche: str,
        rapport: Dict,
        statut_rag: str,
        t_debut: datetime
    ) -> None:
        """Sauvegarde le log d'audit en JSON."""
        log = {
            'audit_id':    audit_id,
            'agent':       'A2_PREPROCESSING',
            'version':     '1.0',
            'timestamp':   t_debut.isoformat(),
            'sous_branche': sous_branche,
            'statut_rag':  statut_rag,
            'etapes':      rapport['etapes'],
            'nb_lignes':   {
                'debut': rapport['nb_lignes_debut'],
                'fin':   rapport.get('nb_lignes_fin', rapport['nb_lignes_debut']),
            },
            'nb_features': {
                'debut':    rapport['nb_cols_debut'],
                'fin':      rapport.get('nb_cols_fin', rapport['nb_cols_debut']),
                'ajoutees': rapport.get('nb_features_ajoutees', 0),
            },
            'features_creees': rapport.get('features_creees', []),
        }
        chemin = self.audit_path / f"{audit_id}.json"
        try:
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(log, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"Audit trail non sauvegardé : {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # STATUT RAG & COMMENTAIRES
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_statut_rag(
        self,
        rapport: Dict,
        df: pd.DataFrame
    ) -> str:
        """
        Calcule le statut RAG du preprocessing.

        VERT  : Données prêtes pour GLM et ML sans restriction
        AMBRE : Données utilisables mais points d'attention
        ROUGE : Preprocessing incomplet — intervention requise
        """
        val = rapport.get('transformations', {}).get('validation', {})

        # ROUGE : données non prêtes pour le GLM
        if not val.get('pret_pour_glm', True):
            return 'ROUGE'

        # ROUGE : NaN restants excessifs
        nan_restants = val.get('nan_restants', 0)
        if nan_restants > len(df) * 0.05:  # > 5% de NaN restants
            return 'ROUGE'

        # AMBRE : colonnes non encodées restantes
        if val.get('colonnes_non_encodees'):
            return 'AMBRE'

        # AMBRE : exposition non validée
        if not val.get('exposition_valide', True):
            return 'AMBRE'

        return 'VERT'

    def _commenter_actuaire_senior(
        self,
        rapport: Dict,
        sous_branche: str,
        statut_rag: str,
        cible_freq: str,
        cible_cout: str,
        df: pd.DataFrame
    ) -> str:
        """
        Commentaire actuaire sénior en 3 niveaux sur le preprocessing.
        """
        emoji = glyphe_rag(statut_rag)
        features_new    = rapport.get('features_creees', [])
        nb_features_new = len(features_new)
        val             = rapport.get('transformations', {}).get('validation', {})
        winsor          = rapport.get('transformations', {}).get('winsorisation', {})
        # ⚠️ `winsorisation` EST DÉJÀ LE DICTIONNAIRE DES COLONNES ÉCRÊTÉES —
        # `_appliquer_plan` y pose {nom_colonne: {borne_inf, borne_sup,
        # n_valeurs_ecretees}}. La clé `colonnes_winsorisees` n'a jamais
        # existé : son `.get(..., {})` rendait toujours un dictionnaire vide,
        # et l'actuaire lisait « Winsorisées : 0 variable(s) » alors que neuf
        # facteurs continus avaient été plafonnés. C'est le compte lui-même
        # qui était faux, pas seulement sa mise en forme.
        nb_winsor       = len(winsor)
        nb_cols_fin     = rapport.get('nb_cols_fin', rapport['nb_cols_debut'])

        # ── NIVEAU 1 : LECTURE ────────────────────────────────────────────────
        niveau1 = (
            f"{emoji} PREPROCESSING {statut_rag}\n"
            f"Sous-branche : {sous_branche}\n"
            f"Lignes       : {rapport['nb_lignes_debut']:,} → "
            f"{rapport.get('nb_lignes_fin', rapport['nb_lignes_debut']):,}\n"
            f"Colonnes     : {rapport['nb_cols_debut']} → {nb_cols_fin} "
            f"(+{nb_features_new} features créées)\n"
            f"Étapes       : {' → '.join(rapport['etapes'])}\n"
            f"Winsorisées  : {nb_winsor} variable(s)\n"
            f"NaN restants : {val.get('nan_restants', 0)}"
        )

        # ── NIVEAU 2 : DIAGNOSTIC ─────────────────────────────────────────────
        if statut_rag == 'VERT':
            niveau2 = (
                "DIAGNOSTIC ACTUARIEL :\n"
                f"Le preprocessing est complet et conforme aux exigences "
                f"de calibration actuarielle. "
                f"Les {nb_features_new} variables créées enrichissent "
                f"le pouvoir prédictif des modèles ML (A4) "
                f"sans introduire de biais dans le GLM (A3). "
                f"L'exposition est validée et le log-offset est prêt "
                f"pour le GLM Poisson. "
                f"La Winsorisation sur {nb_winsor} variable(s) réduit "
                f"l'influence des valeurs extrêmes sur les paramètres β "
                f"du GLM Gamma."
            )
        elif statut_rag == 'AMBRE':
            cols_non_enc = val.get('colonnes_non_encodees', [])
            niveau2 = (
                "DIAGNOSTIC ACTUARIEL :\n"
                f"Le preprocessing principal est réalisé mais "
                f"{len(cols_non_enc)} colonne(s) n'ont pas pu être "
                f"encodées automatiquement : {cols_non_enc}. "
                f"Ces colonnes seront exclues des modèles GLM et ML "
                f"car les algorithmes ne gèrent pas les chaînes de caractères. "
                f"Vérifiez si ces variables sont pertinentes actuariellement "
                f"avant de les ignorer définitivement."
            )
        else:
            niveau2 = (
                "DIAGNOSTIC ACTUARIEL :\n"
                f"Le preprocessing est incomplet. "
                f"Des valeurs manquantes ou incohérentes subsistent "
                f"après traitement. La calibration du GLM Poisson "
                f"produirait des estimateurs biaisés sur ces données."
            )

        # ── NIVEAU 3 : RECOMMANDATION ─────────────────────────────────────────
        if statut_rag == 'VERT':
            niveau3 = (
                "RECOMMANDATION :\n"
                f"→ Passer à l'agent A3 (GLM Poisson + Gamma). \n"
                f"→ Utiliser 'log_exposition' comme offset dans le GLM Poisson.\n"
                f"→ Variable cible fréquence : '{cible_freq}'.\n"
                f"→ Variable cible coût      : '{cible_cout}' "
                f"  (sur les sinistres > 0 uniquement).\n"
                f"→ Les {nb_features_new} nouvelles features sont "
                f"  disponibles pour A4 (ML) et A5 (CANN)."
            )
        elif statut_rag == 'AMBRE':
            niveau3 = (
                "RECOMMANDATION :\n"
                "→ Procéder avec précaution à l'agent A3.\n"
                "→ Les colonnes non encodées seront ignorées par le GLM.\n"
                "→ Investiguer manuellement leur pertinence actuarielle.\n"
                "→ Relancer A2 avec une configuration d'encodage étendue "
                "  si ces colonnes sont importantes."
            )
        else:
            niveau3 = (
                "RECOMMANDATION :\n"
                "→ ARRÊT — Ne pas transmettre à A3.\n"
                "→ Corriger les problèmes identifiés ci-dessus.\n"
                "→ Relancer A1 puis A2 après correction."
            )

        return f"{niveau1}\n\n{niveau2}\n\n{niveau3}"

    def _afficher_rapport_console(
        self,
        audit_id: str,
        sous_branche: str,
        rapport: Dict,
        statut_rag: str,
        commentaire: str
    ) -> None:
        """Affiche le rapport dans la console Colab."""
        emoji = glyphe_rag(statut_rag)
        sep   = "═" * 65

        print(f"\n{sep}")
        print(f"  ACTUARIA — AGENT A2 PREPROCESSING | {audit_id}")
        print(sep)
        print(f"  Sous-branche : {sous_branche}")
        print(f"  {emoji} STATUT : {statut_rag}")
        print(f"\n  TRANSFORMATIONS EFFECTUÉES :")
        for etape in rapport['etapes']:
            print(f"    ✅ {etape}")
        print(f"\n  FEATURES CRÉÉES ({len(rapport.get('features_creees', []))}) :")
        for f in rapport.get('features_creees', [])[:10]:
            print(f"    + {f}")
        if len(rapport.get('features_creees', [])) > 10:
            print(f"    ... et {len(rapport['features_creees'])-10} autres")
        print(f"\n{sep}")
        print("  COMMENTAIRE ACTUAIRE SÉNIOR")
        print(sep)
        for ligne in commentaire.split('\n'):
            print(f"  {ligne}")
        print(sep + "\n")

    def _erreur(self, message: str, audit_id: str) -> Dict:
        """Retourne un résultat d'erreur structuré."""
        return {
            'success':     False,
            'dataframe':   pd.DataFrame(),
            'branche':     None,
            'statut_rag':  'ROUGE',
            'rapport':     {},
            'parametres':  {},
            'commentaire': f"❌ ERREUR A2 : {message}",
            'audit_id':    audit_id,
            'erreur':      message,
        }


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE GOOGLE COLAB
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    """
    Test de l'agent A2 depuis Google Colab.

    Copie ces cellules dans ActuarIA_Phase02_Agent_A2_Preprocessing.ipynb :

    ─────────────────────────────────────────────────────────────────────
    # Cellule 1
    from google.colab import drive
    # drive.mount('/content/drive')  # Colab uniquement

    # Cellule 2
    %run '/tmp/actuaria/agents/a1_ingestion.py'
    %run '/tmp/actuaria/agents/a2_preprocessing.py'
    print("✅ Agents A1 et A2 chargés")

    # Cellule 3 — Chargement avec A1
    agent_a1 = AgentA1Ingestion(
        base_path  = '/tmp/actuaria/data',
        audit_path = '/tmp/actuaria',
        verbose    = False
    )
    result_a1 = agent_a1.run(
        branche = 'non_vie',
        fichier = 'contrats_auto_70k.parquet'
    )
    print(f"A1 : {result_a1['statut_rag']} | {len(result_a1['dataframe']):,} lignes")

    # Cellule 4 — Preprocessing avec A2
    agent_a2 = AgentA2Preprocessing(
        models_path = '/tmp/actuaria',
        audit_path  = '/tmp/actuaria',
        verbose     = True
    )
    result_a2 = agent_a2.run(result_a1)

    # Cellule 5 — Résultats
    df_pret = result_a2['dataframe']
    print(f"Shape final : {df_pret.shape}")
    print(f"Statut      : {result_a2['statut_rag']}")
    print(result_a2['commentaire'])

    # Cellule 6 — Voir les nouvelles features
    print("Features créées :")
    for f in result_a2['rapport']['features_creees']:
        print(f"  + {f}")

    # Cellule 7 — DataFrame final
    df_pret.head(10)
    ─────────────────────────────────────────────────────────────────────
    """
    print("Agent A2 — Preprocessing & Feature Engineering ActuarIA v1.0")
    print("Importez ce module dans votre notebook Colab.")
    print("Exemple : %run 'chemin/a2_preprocessing.py'")
