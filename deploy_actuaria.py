"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              ACTUARIA — SCRIPT DE DÉPLOIEMENT AUTOMATIQUE                   ║
║                        deploy_actuaria.py                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  CE SCRIPT FAIT TOUT AUTOMATIQUEMENT :                                       ║
║  1. Crée toute la structure de dossiers sur Drive                            ║
║  2. Télécharge les agents depuis GitHub (ou les copie depuis Colab)         ║
║  3. Crée les notebooks Colab pour chaque agent                               ║
║  4. Place tout au bon endroit                                                ║
║  5. Vérifie que tout est en ordre                                            ║
║                                                                              ║
║  USAGE DANS GOOGLE COLAB :                                                   ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  from google.colab import drive                                              ║
║  drive.mount('/content/drive')                                               ║
║                                                                              ║
║  # Option 1 : depuis un fichier uploadé dans Colab                          ║
║  %run deploy_actuaria.py                                                     ║
║  deployer()                                                                  ║
║                                                                              ║
║  # Option 2 : copier-coller ce script dans une cellule Colab                ║
║  # et appeler deployer() à la fin                                            ║
║                                                                              ║
║  AUTEUR  : ActuarIA — Système Actuariel IA                                  ║
║  VERSION : 1.0                                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION — CHEMINS
# ══════════════════════════════════════════════════════════════════════════════

# Racine du projet sur Google Drive
DRIVE_ROOT = '/content/drive/MyDrive/ActuarIA'

# Structure complète des dossiers à créer
STRUCTURE_DOSSIERS = {
    'data': {
        'non_vie':          'Données Non-Vie (Auto, MRH, RC Pro)',
        'vie':              'Données Vie (Indiv, Coll, Épargne-Retraite)',
        'sante_prevoyance': 'Données Santé-Prévoyance',
    },
    'agents':       'Code Python des agents actuariels',
    'notebooks':    'Notebooks Google Colab par agent',
    'models':       'Modèles entraînés (.pkl, .json)',
    'reports':      'Rapports générés (PDF, Excel, HTML)',
    'audit':        'Logs d\'audit trail (JSON horodatés)',
    'outputs':      'Sorties intermédiaires et exports',
    'config':       'Fichiers de configuration',
}

# Agents à déployer avec leurs métadonnées
AGENTS = [
    {
        'code':        'A1',
        'nom_fichier': 'a1_ingestion.py',
        'nom_notebook':'ActuarIA_Phase01_Agent_A1_Ingestion',
        'titre':       'Agent A1 — Ingestion & Validation',
        'description': 'Chargement multi-format, détection branche, validation qualité RAG',
        'autonomie':   'Niveau 1',
        'dependances': [],
    },
    {
        'code':        'A2',
        'nom_fichier': 'a2_preprocessing.py',
        'nom_notebook':'ActuarIA_Phase02_Agent_A2_Preprocessing',
        'titre':       'Agent A2 — Preprocessing & Feature Engineering',
        'description': 'Imputation, Winsorisation, Encodage, Exposition, Features métier',
        'autonomie':   'Niveau 2',
        'dependances': ['a1_ingestion.py'],
    },
    {
        'code':        'A3',
        'nom_fichier': 'a3_glm.py',
        'nom_notebook':'ActuarIA_Phase03_Agent_A3_GLM_Tarification',
        'titre':       'Agent A3 — Tarification GLM',
        'description': 'GLM Poisson (fréquence) + Gamma (coût) + Tweedie (prime pure)',
        'autonomie':   'Niveau 2',
        'dependances': ['a1_ingestion.py', 'a2_preprocessing.py'],
    },
    {
        'code':        'A4',
        'nom_fichier': 'a4_ml.py',
        'nom_notebook':'ActuarIA_Phase04_Agent_A4_ML_Tarification',
        'titre':       'Agent A4 — Tarification ML ×8',
        'description': 'GBM · XGBoost · LightGBM · CatBoost · RF · ElasticNet · GAM · Rég.Quantile',
        'autonomie':   'Niveau 2',
        'dependances': ['a1_ingestion.py', 'a2_preprocessing.py'],
    },
    {
        'code':        'A5',
        'nom_fichier': 'a5_deep_learning.py',
        'nom_notebook':'ActuarIA_Phase05_Agent_A5_DeepLearning_CANN',
        'titre':       'Agent A5 — Deep Learning (CANN + TabNet)',
        'description': 'CANN Wüthrich 2019 + TabNet — interprétable par design',
        'autonomie':   'Niveau 2',
        'dependances': ['a1_ingestion.py', 'a2_preprocessing.py'],
    },
    {
        'code':        'A6',
        'nom_fichier': 'a6_comparaison.py',
        'nom_notebook':'ActuarIA_Phase06_Agent_A6_Comparaison_Validation',
        'titre':       'Agent A6 — Comparaison & Validation modèles',
        'description': 'Gini · RMSE · Lift · SHAP · Backtesting · Test A/E',
        'autonomie':   'Niveau 2',
        'dependances': ['a3_glm.py', 'a4_ml.py', 'a5_deep_learning.py'],
    },
    {
        'code':        'A7',
        'nom_fichier': 'a7_provisionnement.py',
        'nom_notebook':'ActuarIA_Phase07_Agent_A7_Provisionnement',
        'titre':       'Agent A7 — Provisionnement',
        'description': 'Chain Ladder · Mack 1993 (IC 95%) · BF · Cape Cod · Prospective · Zillmer · GPV',
        'autonomie':   'Niveau 2',
        'dependances': ['a1_ingestion.py', 'a2_preprocessing.py'],
    },
    {
        'code':        'A8',
        'nom_fichier': 'a8_stress_testing.py',
        'nom_notebook':'ActuarIA_Phase08_Agent_A8_StressTesting_ORSA',
        'titre':       'Agent A8 — Stress Testing & ORSA',
        'description': 'Chocs S2 · Scénarios adverses · ORSA 3-5 ans · Sensibilités',
        'autonomie':   'Niveau 2+',
        'dependances': ['a3_glm.py', 'a7_provisionnement.py'],
    },
    {
        'code':        'A9',
        'nom_fichier': 'a9_coherence.py',
        'nom_notebook':'ActuarIA_Phase09_Agent_A9_Coherence',
        'titre':       'Agent A9 — Cohérence Inter-équipes',
        'description': 'Tarif↔Prov↔S2↔IFRS17 · Alertes RAG · Dashboard temps réel',
        'autonomie':   'Niveau 2+',
        'dependances': ['a3_glm.py', 'a7_provisionnement.py'],
    },
    {
        'code':        'A10',
        'nom_fichier': 'a10_solvabilite2.py',
        'nom_notebook':'ActuarIA_Phase10_Agent_A10_Solvabilite2',
        'titre':       'Agent A10 — Solvabilité 2',
        'description': 'SCR souscription+marché · MCR · QRT · ORSA — Par branche',
        'autonomie':   'Niveau 2',
        'dependances': ['a7_provisionnement.py'],
    },
    {
        'code':        'A11',
        'nom_fichier': 'a11_ifrs17.py',
        'nom_notebook':'ActuarIA_Phase11_Agent_A11_IFRS17',
        'titre':       'Agent A11 — IFRS 17',
        'description': 'PAA (NV≤1an) · BBA+VFA (Vie) · CSM · RA · IAS 19 (Art.39)',
        'autonomie':   'Niveau 2',
        'dependances': ['a7_provisionnement.py'],
    },
    {
        'code':        'A12',
        'nom_fichier': 'a12_alm.py',
        'nom_notebook':'ActuarIA_Phase12_Agent_A12_ALM',
        'titre':       'Agent A12 — ALM & Risque Liquidité',
        'description': 'Duration · Immunisation · Matching · Gap actif-passif',
        'autonomie':   'Niveau 2',
        'dependances': ['a7_provisionnement.py'],
    },
    {
        'code':        'A13',
        'nom_fichier': 'a13_audit.py',
        'nom_notebook':'ActuarIA_Phase13_Agent_A13_AuditTrail',
        'titre':       'Agent A13 — Audit Trail & Versioning',
        'description': 'Log horodaté · Versioning hypothèses · RGPD Art.30 · Reproductibilité',
        'autonomie':   'Niveau 1',
        'dependances': [],
    },
    {
        'code':        'A14',
        'nom_fichier': 'a14_mortalite.py',
        'nom_notebook':'ActuarIA_Phase14_Agent_A14_Mortalite',
        'titre':       'Agent A14 — Tables de Mortalité',
        'description': 'TH/TF 00-02 · TGHF 05 · BCAC · Validation table client · Dérive mortalité',
        'autonomie':   'Niveau 1',
        'dependances': [],
    },
    {
        'code':        'EP1-5',
        'nom_fichier': 'agents_epargne_retraite.py',
        'nom_notebook':'ActuarIA_Phase15_Agents_EP_EpargneRetraite',
        'titre':       'Agents EP1→EP5 — Épargne-Retraite',
        'description': 'Art.39/IAS19 · Art.83/PER · Loi PACTE · Run-off · ALM LT',
        'autonomie':   'Niveau 2',
        'dependances': ['a7_provisionnement.py', 'a14_mortalite.py'],
    },
    {
        'code':        'APP',
        'nom_fichier': 'app_actuaria.py',
        'nom_notebook':'ActuarIA_Phase16_Interface_Plateforme',
        'titre':       'Interface Plateforme ActuarIA',
        'description': 'Interface Streamlit premium · Navigation · Dashboard · Rapports',
        'autonomie':   'N/A',
        'dependances': ['tous les agents'],
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATES NOTEBOOKS COLAB
# ══════════════════════════════════════════════════════════════════════════════

def generer_contenu_notebook(agent: dict) -> dict:
    """
    Génère le contenu d'un notebook Colab (.ipynb) pour un agent.

    Le notebook est pré-rempli avec :
    - Les cellules de configuration (Drive, imports)
    - Les cellules de test de l'agent
    - Les cellules de visualisation des résultats
    """
    code        = agent['code']
    nom_fichier = agent['nom_fichier']
    titre       = agent['titre']
    description = agent['description']
    dependances = agent['dependances']
    autonomie   = agent['autonomie']

    # ── CELLULE 0 : EN-TÊTE (Markdown) ───────────────────────────────────────
    cellule_header = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            f"# 🤖 ActuarIA — {titre}\n",
            f"\n",
            f"**Description :** {description}\n",
            f"\n",
            f"**Autonomie :** {autonomie}\n",
            f"\n",
            f"**Dépendances :** {', '.join(dependances) if dependances else 'Aucune'}\n",
            f"\n",
            f"---\n",
            f"\n",
            f"## 📋 Pipeline\n",
            f"\n",
            f"```\n",
            f"Cellule 1 → Montage Drive\n",
            f"Cellule 2 → Chargement des agents\n",
            f"Cellule 3 → Configuration\n",
            f"Cellule 4 → Exécution de l'agent\n",
            f"Cellule 5 → Résultats et commentaires\n",
            f"Cellule 6 → Visualisation\n",
            f"```\n",
        ]
    }

    # ── CELLULE 1 : MONTAGE DRIVE ─────────────────────────────────────────────
    cellule_drive = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# ── CELLULE 1 : Montage Google Drive ──────────────────────────\n",
            "# Cette cellule doit toujours être exécutée en PREMIER\n",
            "# Une fenêtre pop-up apparaîtra pour autoriser l'accès\n",
            "from google.colab import drive\n",
            "drive.mount('/content/drive')\n",
            "print('✅ Drive monté avec succès')\n",
        ]
    }

    # ── CELLULE 2 : CHARGEMENT AGENTS ─────────────────────────────────────────
    # Génère les lignes %run pour chaque dépendance + l'agent courant
    lignes_run = [
        "# ── CELLULE 2 : Chargement des agents ────────────────────────\n",
        "# Les agents sont chargés dans l'ordre de dépendance\n",
        "\n",
        "AGENTS_PATH = '/content/drive/MyDrive/ActuarIA/agents'\n",
        "\n",
    ]

    # Chargement des dépendances d'abord
    for dep in dependances:
        lignes_run.append(f"%run '/content/drive/MyDrive/ActuarIA/agents/{dep}'\n")

    # Puis l'agent courant
        lignes_run.append(f"%run '/content/drive/MyDrive/ActuarIA/agents/{nom_fichier}'\n")
    lignes_run.append("\n")
    lignes_run.append(f"print('✅ {titre} chargé')\n")

    cellule_agents = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": lignes_run
    }

    # ── CELLULE 3 : CONFIGURATION ─────────────────────────────────────────────
    cellule_config = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# ── CELLULE 3 : Configuration ─────────────────────────────────\n",
            "# Chemins principaux — ne pas modifier\n",
            "\n",
            "BASE_PATH   = '/content/drive/MyDrive/ActuarIA'\n",
            "DATA_PATH   = f'{BASE_PATH}/data'\n",
            "MODELS_PATH = f'{BASE_PATH}/models'\n",
            "AUDIT_PATH  = f'{BASE_PATH}/audit'\n",
            "REPORTS_PATH= f'{BASE_PATH}/reports'\n",
            "\n",
            "# Branche à traiter\n",
            "# Options : 'non_vie', 'vie', 'sante_prevoyance'\n",
            "BRANCHE = 'non_vie'\n",
            "\n",
            "# Fichier à charger\n",
            "# Options Non-Vie  : 'contrats_auto_70k.parquet', 'contrats_mrh_70k.parquet', 'contrats_rcpro_70k.parquet'\n",
            "# Options Vie      : 'contrats_vie_indiv_70k.parquet', 'contrats_art39_70k.parquet'\n",
            "# Options S/P      : 'contrats_sante_coll_70k.parquet', 'contrats_prev_coll_70k.parquet'\n",
            "FICHIER = 'contrats_auto_70k.parquet'\n",
            "\n",
            "print(f'✅ Configuration OK')\n",
            "print(f'   Branche : {BRANCHE}')\n",
            "print(f'   Fichier : {FICHIER}')\n",
        ]
    }

    # ── CELLULE 4 : EXÉCUTION ─────────────────────────────────────────────────
    # Le code d'exécution est spécifique à chaque agent
    cellule_exec = generer_cellule_execution(agent)

    # ── CELLULE 5 : RÉSULTATS ─────────────────────────────────────────────────
    cellule_resultats = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# ── CELLULE 5 : Résultats et commentaire actuaire sénior ──────\n",
            "\n",
            "if result.get('success', False):\n",
            "    print('=' * 65)\n",
            f"    print('  {titre}')\n",
            "    print('=' * 65)\n",
            "    print(f\"  Statut RAG : {result['statut_rag']}\")\n",
            "    print(f\"  Audit ID   : {result['audit_id']}\")\n",
            "    print()\n",
            "    print('  COMMENTAIRE ACTUAIRE SÉNIOR :')\n",
            "    print('  ' + '-' * 60)\n",
            "    for ligne in result['commentaire'].split('\\n'):\n",
            "        print(f'  {ligne}')\n",
            "else:\n",
            "    print(f\"❌ ERREUR : {result.get('erreur', 'Erreur inconnue')}\")\n",
        ]
    }

    # ── CELLULE 6 : VISUALISATION ─────────────────────────────────────────────
    cellule_visu = generer_cellule_visualisation(agent)

    # ── ASSEMBLAGE DU NOTEBOOK ────────────────────────────────────────────────
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.10.0"
            },
            "colab": {
                "name": agent['nom_notebook'],
                "provenance": [],
                "collapsed_sections": []
            }
        },
        "cells": [
            cellule_header,
            cellule_drive,
            cellule_agents,
            cellule_config,
            cellule_exec,
            cellule_resultats,
            cellule_visu,
        ]
    }

    return notebook


def generer_cellule_execution(agent: dict) -> dict:
    """Génère la cellule d'exécution spécifique à chaque agent."""
    code = agent['code']

    # ── A1 : INGESTION ────────────────────────────────────────────────────────
    if code == 'A1':
        source = [
            "# ── CELLULE 4 : Exécution Agent A1 ───────────────────────────\n",
            "\n",
            "agent = AgentA1Ingestion(\n",
            "    base_path  = DATA_PATH,\n",
            "    audit_path = AUDIT_PATH,\n",
            "    verbose    = True\n",
            ")\n",
            "\n",
            "result = agent.run(\n",
            "    branche = BRANCHE,\n",
            "    fichier = FICHIER\n",
            ")\n",
            "\n",
            "# Stockage du résultat pour les agents suivants\n",
            "result_a1 = result\n",
            "df_a1     = result['dataframe']\n",
            "\n",
            "print(f\"Statut : {result['statut_rag']}\")\n",
            "print(f\"Score  : {result['score_qual']:.1f}/100\")\n",
            "print(f\"Lignes : {len(df_a1):,}\")\n",
            "print(f\"Shape  : {df_a1.shape}\")\n",
        ]

    # ── A2 : PREPROCESSING ────────────────────────────────────────────────────
    elif code == 'A2':
        source = [
            "# ── CELLULE 4 : Exécution Agents A1 + A2 ─────────────────────\n",
            "\n",
            "# Étape 1 : Chargement avec A1\n",
            "agent_a1 = AgentA1Ingestion(\n",
            "    base_path  = DATA_PATH,\n",
            "    audit_path = AUDIT_PATH,\n",
            "    verbose    = False\n",
            ")\n",
            "result_a1 = agent_a1.run(branche=BRANCHE, fichier=FICHIER)\n",
            "print(f\"A1 : {result_a1['statut_rag']} | {len(result_a1['dataframe']):,} lignes\")\n",
            "\n",
            "# Étape 2 : Preprocessing avec A2\n",
            "agent_a2 = AgentA2Preprocessing(\n",
            "    models_path = MODELS_PATH,\n",
            "    audit_path  = AUDIT_PATH,\n",
            "    verbose     = True\n",
            ")\n",
            "result = agent_a2.run(result_a1)\n",
            "result_a2 = result\n",
            "df_a2     = result['dataframe']\n",
            "\n",
            "print(f\"A2 : {result['statut_rag']}\")\n",
            "print(f\"Shape : {df_a2.shape}\")\n",
            "print(f\"Features créées : {len(result['rapport']['features_creees'])}\")\n",
        ]

    # ── AUTRES AGENTS (template générique) ────────────────────────────────────
    else:
        nom_classe = f"Agent{code.replace('-','')}"
        source = [
            f"# ── CELLULE 4 : Exécution {agent['titre']} ──────────────\n",
            "# ⚠️ Cet agent sera disponible dans une prochaine version\n",
            "# La cellule sera complétée automatiquement lors du déploiement\n",
            "\n",
            "print(f\"Agent {code} en cours de développement...\")\n",
            "print(f\"Titre : {agent['titre']}\")\n",
            "print(f\"Description : {agent['description']}\")\n",
            "\n",
            "# Placeholder pour le résultat\n",
            "result = {'success': False, 'statut_rag': 'N/A',\n",
            "          'commentaire': 'Agent en développement',\n",
            "          'audit_id': 'N/A', 'erreur': None}\n",
        ]

    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source
    }


def generer_cellule_visualisation(agent: dict) -> dict:
    """Génère la cellule de visualisation des résultats."""
    code = agent['code']

    if code == 'A1':
        source = [
            "# ── CELLULE 6 : Visualisation ────────────────────────────────\n",
            "\n",
            "if result.get('success'):\n",
            "    df_a1.head(10)\n",
        ]
    elif code == 'A2':
        source = [
            "# ── CELLULE 6 : Visualisation features créées ────────────────\n",
            "\n",
            "if result.get('success'):\n",
            "    import pandas as pd\n",
            "    print('NOUVELLES FEATURES CRÉÉES :')\n",
            "    for f in result['rapport']['features_creees']:\n",
            "        if f in df_a2.columns:\n",
            "            print(f'  + {f:<40} | moy={df_a2[f].mean():.3f}')\n",
            "    print()\n",
            "    df_a2.head(10)\n",
        ]
    else:
        source = [
            "# ── CELLULE 6 : Visualisation ────────────────────────────────\n",
            "print('Visualisation disponible après développement complet')\n",
        ]

    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source
    }


# ══════════════════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE DE DÉPLOIEMENT
# ══════════════════════════════════════════════════════════════════════════════

def deployer(
    drive_root:     str = DRIVE_ROOT,
    agents_source:  str = None,
    creer_notebooks: bool = True,
    verbose:         bool = True
) -> dict:
    """
    Déploie toute la structure ActuarIA sur Google Drive.

    Paramètres
    ──────────
    drive_root : str
        Chemin racine sur Drive. Par défaut : /content/drive/MyDrive/ActuarIA

    agents_source : str, optionnel
        Dossier contenant les fichiers .py des agents.
        Si None, cherche dans /content/ (fichiers uploadés dans Colab)

    creer_notebooks : bool
        Si True, crée les notebooks Colab pour chaque agent.

    verbose : bool
        Affiche le détail des opérations.

    Retourne
    ────────
    dict avec le résumé du déploiement
    """
    t_debut  = datetime.now()
    root     = Path(drive_root)
    rapport  = {
        'timestamp':          t_debut.isoformat(),
        'dossiers_crees':     [],
        'agents_deployes':    [],
        'notebooks_crees':    [],
        'erreurs':            [],
    }

    print("\n" + "═" * 65)
    print("  ACTUARIA — DÉPLOIEMENT AUTOMATIQUE")
    print(f"  {t_debut.strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 65)

    # ── ÉTAPE 1 : CRÉATION DE LA STRUCTURE DE DOSSIERS ───────────────────────
    print("\n  📁 ÉTAPE 1 : Création de la structure de dossiers")
    print("  " + "─" * 55)

    def creer_dossier(chemin: Path, description: str = ""):
        """Crée un dossier s'il n'existe pas et logue le résultat."""
        if chemin.exists():
            if verbose:
                print(f"     ⏭️  {chemin.name:<30} (déjà présent)")
        else:
            chemin.mkdir(parents=True, exist_ok=True)
            rapport['dossiers_crees'].append(str(chemin))
            if verbose:
                print(f"     ✅ {chemin.name:<30} créé")

    # Création récursive de la structure
    for nom, contenu in STRUCTURE_DOSSIERS.items():
        chemin_principal = root / nom
        creer_dossier(chemin_principal)

        # Sous-dossiers si c'est un dict
        if isinstance(contenu, dict):
            for sous_nom in contenu:
                creer_dossier(chemin_principal / sous_nom)

    # Dossiers supplémentaires
    creer_dossier(root / 'notebooks_v1_archive')

    # ── ÉTAPE 2 : DÉPLOIEMENT DES AGENTS ─────────────────────────────────────
    print(f"\n  🤖 ÉTAPE 2 : Déploiement des agents")
    print("  " + "─" * 55)

    # Recherche des fichiers agents
    # Ordre de priorité :
    # 1. Dossier source spécifié
    # 2. /content/ (fichiers uploadés dans Colab)
    # 3. Dossier agents Drive existant
    dossiers_source = []
    if agents_source:
        dossiers_source.append(Path(agents_source))
    dossiers_source.append(Path('/content'))
    dossiers_source.append(root / 'agents')

    agents_path = root / 'agents'

    for agent in AGENTS:
        nom_fichier = agent['nom_fichier']
        dest        = agents_path / nom_fichier

        # Recherche du fichier source
        source_trouvee = None
        for dossier in dossiers_source:
            candidat = dossier / nom_fichier
            if candidat.exists() and str(candidat) != str(dest):
                source_trouvee = candidat
                break

        if source_trouvee:
            try:
                shutil.copy2(source_trouvee, dest)
                rapport['agents_deployes'].append(nom_fichier)
                print(f"     ✅ {nom_fichier:<40} déployé")
            except Exception as e:
                rapport['erreurs'].append(f"{nom_fichier} : {e}")
                print(f"     ❌ {nom_fichier:<40} ERREUR : {e}")
        elif dest.exists():
            print(f"     ⏭️  {nom_fichier:<40} déjà présent")
        else:
            print(f"     ⏸️  {nom_fichier:<40} en attente (pas encore développé)")

    # ── ÉTAPE 3 : CRÉATION DES NOTEBOOKS ─────────────────────────────────────
    if creer_notebooks:
        print(f"\n  📓 ÉTAPE 3 : Création des notebooks Colab")
        print("  " + "─" * 55)

        notebooks_path = root / 'notebooks'

        for agent in AGENTS:
            nom_notebook = agent['nom_notebook']
            chemin_nb    = notebooks_path / f"{nom_notebook}.ipynb"

            if chemin_nb.exists():
                print(f"     ⏭️  {nom_notebook[:50]}")
                continue

            try:
                # Génération du contenu du notebook
                contenu = generer_contenu_notebook(agent)

                # Sauvegarde en JSON (format ipynb)
                with open(chemin_nb, 'w', encoding='utf-8') as f:
                    json.dump(contenu, f, indent=2, ensure_ascii=False)

                rapport['notebooks_crees'].append(nom_notebook)
                print(f"     ✅ {nom_notebook[:50]}")

            except Exception as e:
                rapport['erreurs'].append(f"Notebook {nom_notebook} : {e}")
                print(f"     ❌ {nom_notebook[:50]} — ERREUR : {e}")

    # ── ÉTAPE 4 : FICHIER DE CONFIGURATION ───────────────────────────────────
    print(f"\n  ⚙️  ÉTAPE 4 : Fichier de configuration")
    config = {
        'actuaria_version': '2.0',
        'drive_root':       str(root),
        'timestamp':        t_debut.isoformat(),
        'chemins': {
            'data':          str(root / 'data'),
            'agents':        str(root / 'agents'),
            'notebooks':     str(root / 'notebooks'),
            'models':        str(root / 'models'),
            'reports':       str(root / 'reports'),
            'audit':         str(root / 'audit'),
        },
        'agents_disponibles': [
            a['nom_fichier'] for a in AGENTS
            if (root / 'agents' / a['nom_fichier']).exists()
        ],
        'tables_mortalite_defaut': {
            'vie_rentes':    'TH_00_02 / TF_00_02',
            'vie_deces':     'TGHF_05_H / TGHF_05_F',
            'sante_prev':    'BCAC + TGHF_05',
        },
    }

    config_path = root / 'config' / 'actuaria_config.json'
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"     ✅ actuaria_config.json créé")
    except Exception as e:
        print(f"     ❌ Config non créée : {e}")

    # ── BILAN FINAL ───────────────────────────────────────────────────────────
    duree = (datetime.now() - t_debut).total_seconds()

    print(f"\n{'═' * 65}")
    print(f"  BILAN DU DÉPLOIEMENT")
    print(f"{'═' * 65}")
    print(f"  ✅ Dossiers créés    : {len(rapport['dossiers_crees'])}")
    print(f"  ✅ Agents déployés   : {len(rapport['agents_deployes'])}")
    print(f"  ✅ Notebooks créés   : {len(rapport['notebooks_crees'])}")
    print(f"  ❌ Erreurs           : {len(rapport['erreurs'])}")
    print(f"  ⏱️  Durée             : {duree:.1f}s")

    if rapport['erreurs']:
        print(f"\n  ERREURS DÉTECTÉES :")
        for err in rapport['erreurs']:
            print(f"    • {err}")

    print(f"\n  📁 Structure créée dans :")
    print(f"     {drive_root}")
    print(f"\n  PROCHAINES ÉTAPES :")
    print(f"  1. Ouvre ActuarIA/notebooks/ dans Drive")
    print(f"  2. Double-clic sur un notebook → s'ouvre dans Colab")
    print(f"  3. Exécute cellule par cellule")
    print("═" * 65 + "\n")

    return rapport


def verifier_deploiement(drive_root: str = DRIVE_ROOT) -> None:
    """
    Vérifie que le déploiement est complet et correct.
    Affiche un rapport détaillé de l'état de chaque composant.
    """
    root = Path(drive_root)

    print("\n" + "═" * 65)
    print("  ACTUARIA — VÉRIFICATION DU DÉPLOIEMENT")
    print("═" * 65)

    # Vérification dossiers
    print("\n  📁 DOSSIERS :")
    dossiers_requis = [
        'data/non_vie', 'data/vie', 'data/sante_prevoyance',
        'agents', 'notebooks', 'models', 'reports', 'audit', 'config'
    ]
    for d in dossiers_requis:
        chemin = root / d
        statut = "✅" if chemin.exists() else "❌"
        print(f"     {statut} {d}")

    # Vérification agents
    print("\n  🤖 AGENTS :")
    for agent in AGENTS:
        chemin = root / 'agents' / agent['nom_fichier']
        if chemin.exists():
            taille = chemin.stat().st_size / 1024
            print(f"     ✅ {agent['nom_fichier']:<45} {taille:.0f} Ko")
        else:
            statut = "⏸️ " if agent['code'] not in ['A1', 'A2'] else "❌"
            print(f"     {statut} {agent['nom_fichier']:<45} manquant")

    # Vérification notebooks
    print("\n  📓 NOTEBOOKS :")
    for agent in AGENTS:
        chemin = root / 'notebooks' / f"{agent['nom_notebook']}.ipynb"
        statut = "✅" if chemin.exists() else "⏸️ "
        print(f"     {statut} {agent['nom_notebook'][:55]}")

    # Vérification données
    print("\n  📊 DONNÉES :")
    fichiers_data = {
        'non_vie': ['contrats_auto_70k.parquet', 'contrats_mrh_70k.parquet',
                    'contrats_rcpro_70k.parquet'],
        'vie': ['contrats_vie_indiv_70k.parquet', 'contrats_art39_70k.parquet'],
        'sante_prevoyance': ['contrats_sante_coll_70k.parquet',
                              'contrats_prev_coll_70k.parquet'],
    }
    for branche, fichiers in fichiers_data.items():
        for f in fichiers:
            chemin = root / 'data' / branche / f
            if chemin.exists():
                taille = chemin.stat().st_size / (1024*1024)
                print(f"     ✅ {branche}/{f:<40} {taille:.1f} Mo")
            else:
                print(f"     ❌ {branche}/{f:<40} manquant")

    print("═" * 65 + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    """
    USAGE DANS GOOGLE COLAB :
    ─────────────────────────────────────────────────────────────────────────
    # Cellule 1 — Monter Drive
    from google.colab import drive
    drive.mount('/content/drive')

    # Cellule 2 — Uploader ce fichier dans Colab (icône upload à gauche)
    # puis exécuter :
    %run deploy_actuaria.py

    # Cellule 3 — Lancer le déploiement
    deployer()

    # Cellule 4 — Vérifier
    verifier_deploiement()
    ─────────────────────────────────────────────────────────────────────────
    """
    print("Script de déploiement ActuarIA v2.0")
    print("Fonctions disponibles :")
    print("  deployer()            → Déploie toute la structure")
    print("  verifier_deploiement()→ Vérifie l'état du déploiement")
