"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              ACTUARIA — AGENT A5 : DEEP LEARNING (CANN + TabNet)            ║
║                        Version 1.0 — Production                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  MODÈLES CALIBRÉS :                                                          ║
║                                                                              ║
║  1. CANN (Combined Actuarial Neural Network) — Wüthrich 2019                ║
║     Architecture : GLM couche entrée + réseau résiduel                      ║
║     Le GLM fournit les prédictions de base, le réseau corrige               ║
║     les résidus non-linéaires que le GLM ne capte pas.                     ║
║     Interprétable : les coefficients GLM restent lisibles.                  ║
║                                                                              ║
║  2. TabNet — Arik & Pfister (Google, 2021)                                  ║
║     Architecture : attention séquentielle sur données tabulaires            ║
║     Sélectionne automatiquement les features importantes                    ║
║     à chaque étape de décision. Interprétable par design.                  ║
║                                                                              ║
║  AUTONOMIE : Niveau 2                                                        ║
║  AUTEUR    : ActuarIA v1.0                                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os, json, pickle, logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import StandardScaler

# Module de conformité partagé (audit V7 BLOQUANT #1) — A5 n'avait AUCUN
# filtre genre avant ce correctif, avec exactement la même logique de
# sélection de features qu'A4 (fuite confirmée par analogie et lecture ;
# exécution DL bloquée dans l'environnement d'audit V7 par l'absence de
# PyTorch, mais la logique de sélection est identique à celle d'A4,
# vérifiée empiriquement).
from core.charts_tarif import (
    FOND_SOMBRE,
    couleur_rag,
    couleur_texte_rag,
    glyphe_rag,
)
from core.conformite_reglementaire import (
    BASE_GINI_COMPTAGE, BASE_GINI_UNITAIRE,
    construire_matrice_x,
)
from core.plan_tarifaire import (
    PlanTarifaire, verifier_completude_plan, plafonner_statut_si_ampute,
    alerte_modele_ampute,
)

# Export Excel (audit V7 MINEUR #2) — A5 était le seul agent sans export
# Excel. export_excel_a5 suit le même gabarit que les autres agents.
try:
    from .services.tarif_excel import export_excel_a5
    TARIF_EXCEL_OK_A5 = True
except ImportError:
    try:
        from direction_non_vie.tarification.services.tarif_excel import export_excel_a5
        TARIF_EXCEL_OK_A5 = True
    except ImportError:
        TARIF_EXCEL_OK_A5 = False

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

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_OK = True
except ImportError:
    TORCH_OK = False
    # Fallback — permet l'import du module sans PyTorch
    # Les classes nn.Module sont inaccessibles mais l'import ne plante pas
    class _FakeModule:
        class Module: pass
        class Linear: pass
        class ReLU: pass
        class Dropout: pass
        class Sequential: pass
        class ModuleList: pass
        class BatchNorm1d: pass
        class Softmax: pass
        @staticmethod
        def init(): pass
    nn = _FakeModule()
    # Fallback torch pour les type hints au niveau classe
    class _FakeTorch:
        class device: pass
        class Tensor: pass
    torch = _FakeTorch()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('actuaria.a5')


# ── Alignement A5 sur le plan signé (Phase 1) ─────────────────────────────────
# Plus de _LOBS_ALIGNES_PLAN ni de chargement de plan EN INTERNE : A5.run() reçoit
# le PLAN signé et le transmet à construire_matrice_x (liste blanche =
# plan.colonnes_produites()). GLM (A3), ML (A4) et DL (A5) partagent EXACTEMENT la
# même curation. NB CANN : la référence GLM du CANN vient de result_a3 (objet A3
# déjà ajusté), appariée PAR NOM contre ces features plan-restreintes — donc
# cohérente dès lors que le caller passe le même plan à A3 et A5. Historiquement
# data-driven (sur-ensemble du plan), déployé LoB par LoB via un frozenset ;
# désormais universel et explicite. Plan absent → erreur propre (voir run()),
# jamais de repli.

# ── COLONNES À EXCLURE ────────────────────────────────────────────────────────
COLS_A_EXCLURE = [
    'id_contrat', 'id_assure', 'id_salarie', 'id_beneficiaire', 'id_adherent',
    'date_souscription', 'date_survenance', 'annee_souscription',
    'nb_sinistres', 'cout_total_sinistres', 'prime_commerciale',
    'lambda_freq_annuel', 'cout_moyen_attendu',
    'exposition', 'log_exposition',
    'prime_pure_annuelle', 'cotisation_annuelle', 'cotisation_mensuelle_eur',
    'charge_annuelle_eur', 'charge_ij_annuelle_eur',
]

COLS_CONTAMINEES = [
    'log_cout', 'log_prime', 'cout_moyen_attendu',
    'lambda_freq', 'prime_pure_obs',
]


# ══════════════════════════════════════════════════════════════════════════════
# ARCHITECTURE CANN
# ══════════════════════════════════════════════════════════════════════════════

class CANNModel(nn.Module):
    """
    Combined Actuarial Neural Network (CANN) — Wüthrich & Merz (2019).

    ARCHITECTURE :
    ─────────────
    Input X → [Couche GLM GELÉE]      → prédiction GLM (log-link) + offset
           ↘ [Réseau résiduel]        → correction non-linéaire
           → Somme → exp() → Prime pure prédite

    CONTRAT WÜTHRICH (audit V4 — implémentation corrigée) :
    ──────────────────────────────────────────────────────
    1. La couche GLM (`glm_layer`) est chargée avec les coefficients d'un
       GLM Tweedie déjà calibré et validé par l'agent A3 (statsmodels),
       PUIS GELÉE (`requires_grad=False`) : elle n'est JAMAIS mise à jour
       par la descente de gradient. Les poids que l'on peut extraire de
       cette couche à tout moment de l'entraînement sont donc STRICTEMENT
       IDENTIQUES aux coefficients du GLM déjà audité — pas une
       approximation, pas un point de départ qui dérive.
    2. La dernière couche du réseau résiduel est initialisée à zéro
       (poids ET biais). Conséquence : à l'époque 0, avant tout
       entraînement, `résiduel(x) = 0` pour tout x, donc
       CANN(x) = exp(GLM_gelé(x) + offset) = prédiction GLM exacte.
       Le réseau ne fait qu'ajouter une correction à ce point de départ.
    3. L'offset (log de l'exposition) est ajouté explicitement dans
       `forward()`, à l'identique de la sémantique statsmodels
       (`GLM.predict(X, offset=...)`) — il ne s'agit PAS d'un poids
       entraînable, c'est un terme additif fixe du prédicteur linéaire.

    Si aucun GLM n'est fourni (`glm_weight_init=None`), la couche
    `glm_layer` reste librement entraînable — dans ce cas le modèle N'EST
    PAS un CANN au sens de Wüthrich et ne doit pas être présenté comme
    interprétable pour l'audit S2 (voir `glm_gele` dans les métriques).

    Réf. : Wüthrich, M.V. & Merz, M. (2019), "Editorial: Yes, we CANN!",
           ASTIN Bulletin 49(1).
    """

    def __init__(
        self,
        n_features:      int,
        hidden_sizes:    List[int] = [64, 32],
        glm_weight_init: Optional[np.ndarray] = None,
        glm_bias_init:   Optional[float] = None,
    ):
        super().__init__()

        # Couche GLM — équivalent d'une régression linéaire log-link
        self.glm_layer = nn.Linear(n_features, 1)

        # Réseau résiduel — capture les effets non-linéaires
        layers = []
        in_size = n_features
        for h in hidden_sizes:
            layers.extend([
                nn.Linear(in_size, h),
                nn.ReLU(),
                nn.Dropout(0.2),  # Régularisation → évite l'overfitting
            ])
            in_size = h
        layers.append(nn.Linear(in_size, 1))
        self.residual_net = nn.Sequential(*layers)

        # Initialisation des poids (couches cachées du résiduel uniquement)
        # Justification : initialisation He pour ReLU → convergence stable
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                nn.init.zeros_(m.bias)

        # ── Init/gel de la couche GLM depuis un GLM calibré (Wüthrich) ───────
        self.glm_gele = False
        if glm_weight_init is not None and glm_bias_init is not None:
            with torch.no_grad():
                self.glm_layer.weight.copy_(
                    torch.FloatTensor(glm_weight_init).unsqueeze(0)
                )
                self.glm_layer.bias.copy_(
                    torch.FloatTensor([glm_bias_init])
                )
            self.glm_layer.weight.requires_grad = False
            self.glm_layer.bias.requires_grad   = False
            self.glm_gele = True

        # ── Init ZÉRO de la dernière couche du résiduel (Wüthrich) ───────────
        # À l'époque 0, résiduel(x) = 0 pour tout x → CANN démarre exactement
        # à la prédiction du GLM (gelé ou non).
        derniere_couche = self.residual_net[-1]
        with torch.no_grad():
            nn.init.zeros_(derniere_couche.weight)
            nn.init.zeros_(derniere_couche.bias)

    def forward(self, x, offset=None):
        # Prédiction GLM (espace log)
        glm_pred = self.glm_layer(x)

        # Offset (log-exposition) — terme additif fixe, PAS un poids entraîné.
        # Réf. sémantique : statsmodels GLM.predict(X, offset=...)
        if offset is not None:
            if offset.dim() == 1:
                offset = offset.unsqueeze(1)
            glm_pred = glm_pred + offset

        # Correction résiduelle (espace log)
        residual = self.residual_net(x)

        # Somme dans l'espace log → exponentielle pour obtenir la prime
        # La prime est toujours positive car exp() > 0
        output = torch.exp(glm_pred + residual)

        return output.squeeze()



# ══════════════════════════════════════════════════════════════════════════════
# ARCHITECTURE TABNET (simplifiée)
# ══════════════════════════════════════════════════════════════════════════════

class TabNetSimple(nn.Module):
    """
    TabNet simplifié — attention séquentielle sur données tabulaires.

    ARCHITECTURE :
    ─────────────
    À chaque étape de décision, le modèle sélectionne
    un sous-ensemble de features via un mécanisme d'attention.
    Chaque étape contribue à la prédiction finale.

    JUSTIFICATION :
    ────────────────
    TabNet est interprétable par design :
    L'importance de chaque feature = somme des poids d'attention
    sur toutes les étapes. C'est une alternative aux SHAP values
    pour justifier le modèle (AI Act 2025).

    NOTE : Cette implémentation est une version simplifiée.
    La version complète (pytorch-tabnet) est disponible via pip.
    """

    def __init__(
        self,
        n_features:  int,
        n_steps:     int = 3,
        hidden_size: int = 64,
    ):
        super().__init__()
        self.n_steps     = n_steps
        self.n_features  = n_features

        # Couche de normalisation des entrées (BN)
        self.bn_input = nn.BatchNorm1d(n_features)

        # Étapes de décision avec mécanisme d'attention
        self.attention_layers = nn.ModuleList([
            nn.Linear(n_features, n_features)
            for _ in range(n_steps)
        ])

        # Couches de transformation par étape
        self.step_layers = nn.ModuleList([
            nn.Sequential(
                nn.Linear(n_features, hidden_size),
                nn.BatchNorm1d(hidden_size),
                nn.ReLU(),
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
            )
            for _ in range(n_steps)
        ])

        # Couche de sortie
        self.output_layer = nn.Linear(hidden_size // 2, 1)

        # Stockage des poids d'attention (pour l'interprétabilité)
        self.attention_weights = []

    def forward(self, x):
        x_norm = self.bn_input(x)

        # Prior scale — pénalise les features déjà sélectionnées
        prior_scale = torch.ones(x.shape[0], self.n_features).to(x.device)

        step_outputs = []
        self.attention_weights = []

        for step in range(self.n_steps):
            # Calcul des poids d'attention
            attn_raw    = self.attention_layers[step](x_norm * prior_scale)
            attn_weight = torch.softmax(attn_raw, dim=-1)
            self.attention_weights.append(attn_weight.detach())

            # Mise à jour du prior scale (pénalise features déjà utilisées)
            prior_scale = prior_scale * (1 - attn_weight + 1e-6)

            # Feature masking
            masked_x = x_norm * attn_weight

            # Transformation
            step_out = self.step_layers[step](masked_x)
            step_outputs.append(step_out)

        # Agrégation des sorties par étape
        aggregated = torch.stack(step_outputs, dim=0).mean(dim=0)

        # Prédiction finale (toujours positive via exp)
        output = torch.exp(self.output_layer(aggregated))

        return output.squeeze()

    def get_feature_importance(self, feature_names: List[str]) -> Dict:
        """
        Calcule l'importance des features à partir des poids d'attention.
        C'est la force principale de TabNet : interprétabilité native.
        """
        if not self.attention_weights:
            return {}

        # Moyenne des poids d'attention sur toutes les étapes
        all_weights = torch.stack(self.attention_weights, dim=0)
        importance  = all_weights.mean(dim=(0, 1)).numpy()

        return {
            name: round(float(imp), 4)
            for name, imp in zip(
                feature_names[:len(importance)],
                importance
            )
        }


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE : AGENT A5
# ══════════════════════════════════════════════════════════════════════════════

class AgentA5DeepLearning:
    """
    Agent A5 — Deep Learning (CANN + TabNet).

    EXEMPLE D'UTILISATION :
    ─────────────────────────
    agent_a5 = AgentA5DeepLearning(
        models_path = '/tmp/actuaria',
        audit_path  = '/tmp/actuaria',
    )
    result_a5 = agent_a5.run(result_a2, result_a3=result_a3, result_a4=result_a4)
    """

    def __init__(
        self,
        models_path: str = '/tmp/actuaria',
        audit_path:  str = '/tmp/actuaria',
        verbose:     bool = True
    ):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.verbose     = verbose

        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)

        self.modeles   = {}
        self.metriques = {}
        self.scalers   = {}

        if not TORCH_OK:
            logger.warning(
                "PyTorch non installé. "
                "Exécutez : !pip install torch"
            )

        if self.verbose:
            logger.info(
                f"Agent A5 Deep Learning initialisé | "
                f"PyTorch={'OK' if TORCH_OK else 'NON INSTALLÉ'} | "
                f"Device={'cuda' if TORCH_OK and torch.cuda.is_available() else 'cpu'}"
            )

    # ══════════════════════════════════════════════════════════════════════════
    # MÉTHODE PRINCIPALE
    # ══════════════════════════════════════════════════════════════════════════

    def run(
        self,
        result_a2:      Dict[str, Any],
        result_a3:      Optional[Dict] = None,
        result_a4:      Optional[Dict] = None,
        col_cible:      Optional[str] = None,   # Phase 2 : OBLIGATOIRE (cf. run())
        col_exposition: str = 'exposition',
        plan:           Optional[PlanTarifaire] = None,   # Phase 1 : plan signé explicite
        modeles:        Tuple[str, ...] = ('cann', 'tabnet'),
        n_epochs:       int = 200,  # Early stopping actif — arrêt automatique
        batch_size:     int = 512,
        learning_rate:      float = 1e-3,
        generer_graphiques: bool  = True,
        seed:               int   = 42,
    ) -> Dict[str, Any]:
        """
        Pipeline Deep Learning complet.

        Paramètres
        ──────────
        col_cible : str
            OBLIGATOIRE — la cible sur laquelle CES modèles DL sont ajustés.
            Ex. 'nb_sinistres' (fréquence) ou 'cout_moyen' (sévérité).
            ⚠ Le défaut historique était 'prime_pure' : INCOHÉRENT avec
            l'architecture du CANN, et jamais utilisé par les appelants (tous
            passaient 'nb_sinistres') — sauf la page prime_dl de l'app, qui
            héritait donc du défaut. Un défaut que personne n'utilise et qui
            contredit l'architecture est un piège : il est supprimé. Absent →
            erreur propre, comme plan=.

        n_epochs : int
            Nombre d'époques d'entraînement.
            50 époques = bon compromis vitesse/performance sur Colab CPU.
            Augmenter à 100-200 sur Colab Pro GPU.

        batch_size : int
            Taille des mini-batches.
            512 = standard pour données actuarielles tabulaires.

        learning_rate : float
            Taux d'apprentissage initial (Adam optimizer).
            1e-3 = valeur par défaut recommandée par Adam.
        """
        t_debut      = datetime.now()
        audit_id     = f"A5_{t_debut.strftime('%Y%m%d_%H%M%S')}"
        sous_branche = result_a2.get('branche', 'inconnue')

        logger.info(f"[{audit_id}] Agent A5 DL démarré | branche={sous_branche}")

        if not TORCH_OK:
            return self._erreur(
                "PyTorch non installé. Exécutez : !pip install torch",
                audit_id
            )

        if not result_a2.get('success', False):
            return self._erreur("L'agent A2 a échoué.", audit_id)

        # Phase 1 : A5 restreint ses features à plan.colonnes_produites() via
        # construire_matrice_x — plus de _LOBS_ALIGNES_PLAN. Plan absent → erreur
        # propre, JAMAIS de repli silencieux.
        if plan is None:
            return self._erreur(
                "A5.run exige un plan (PlanTarifaire) : les features DL sont "
                "restreintes à plan.colonnes_produites() (Phase 1, _LOBS_ALIGNES_PLAN "
                "supprimé). Fournissez plan=PlanTarifaire.depuis_yaml('plans/<lob>.yaml').",
                audit_id)

        # ── LA CIBLE EST DÉCLARÉE, PAS HÉRITÉE D'UN DÉFAUT ───────────────────
        # Le défaut historique 'prime_pure' contredisait l'architecture du CANN :
        # celui-ci est exp(GLM_gelé(x) + offset·log(exposition)) — un modèle de
        # COMPTAGE. La prime pure est exposure-INDÉPENDANTE : l'offset y est non
        # seulement inutile, il est faux, et il dégrade l'ancrage. Aucun appelant
        # n'utilisait ce défaut (tous passaient 'nb_sinistres') — SAUF la page
        # prime_dl de l'app, qui en héritait silencieusement et faisait donc
        # tourner le CANN sur une cible que son archi ne supporte pas.
        # Un défaut que personne n'utilise et qui contredit l'architecture est un
        # piège, pas une commodité : il est supprimé.
        if not col_cible:
            return self._erreur(
                "A5.run exige col_cible : la cible des modèles DL est DÉCLARÉE, "
                "jamais héritée d'un défaut (l'ancien défaut 'prime_pure' était "
                "incohérent avec l'offset log(exposition) du CANN). Ex. "
                "col_cible='nb_sinistres' (fréquence) ou 'cout_moyen' (sévérité).",
                audit_id)

        df      = result_a2['dataframe'].copy()
        rapport = {'etapes': [], 'alertes': []}

        # ── REPRODUCTIBILITÉ — LE SEED EST DÉCLARÉ, PAS SUBI ─────────────────
        # ⚠️⚠️ MESURÉ AVANT CE CORRECTIF : trois exécutions strictement
        # identiques rendaient TabNet à 0,2158 · 0,2379 · 0,2420 — une étendue
        # de 0,0262, soit **11 % de la moyenne**. Le CANN, lui, ne bougeait que
        # de 0,5 % (il est ancré sur un GLM gelé). Or c'est sur ce Gini qu'A6
        # ARBITRE : deux exécutions du même portefeuille pouvaient retenir deux
        # modèles différents, et le dépôt écrit ailleurs « Exigence S2 : tout
        # calcul actuariel doit être reproductible ».
        #
        # ⚠️ Le seed est un PARAMÈTRE, pas une constante cachée : il est
        # déclaré, surchargeable, et inscrit dans les métriques — un actuaire
        # qui rejoue un tarif doit pouvoir le retrouver. Il est posé ICI, dans
        # `run()`, et jamais au niveau module : un module qui fixe l'aléa du
        # process à l'import est le défaut a1/C6, sous un autre nom.
        #
        # ⚠️⚠️ CE QU'IL GOUVERNE, ET CE QU'IL NE GOUVERNE PAS. Il gouverne
        # l'initialisation des poids et le brassage des batches. Il ne
        # gouverne PAS le découpage des jeux : `_preparer_donnees` garde un
        # `random_state=42` fixe, DÉLIBÉRÉMENT. Une partition qui suivrait le
        # seed changerait le jeu de TEST d'une exécution à l'autre — comparer
        # deux seeds ne voudrait alors plus rien dire, puisqu'on ne mesurerait
        # plus sur le même échantillon. La partition est une propriété du
        # PROTOCOLE, l'aléa d'optimisation est une propriété du CALIBRAGE.
        torch.manual_seed(seed)
        np.random.seed(seed)
        rapport['seed'] = int(seed)

        # Device (GPU si disponible, sinon CPU)
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Device : {device}")

        try:
            # ── PRÉPARATION ───────────────────────────────────────────────────
            logger.info(f"[{audit_id}] Préparation données")
            (X_train, X_val, X_test, y_train, y_val, y_test, feature_names,
             expo_train, expo_val, expo_test) = \
                self._preparer_donnees(df, sous_branche, col_cible, col_exposition, plan)
            rapport['etapes'].append('preparation')
            rapport['n_train'] = len(X_train)
            rapport['n_val']   = len(X_val)
            rapport['n_test']  = len(X_test)
            rapport['n_features']    = len(feature_names)
            rapport['feature_names'] = feature_names

            # ── CANN ──────────────────────────────────────────────────────────
            # ⚠ Le CANN n'est PAS calibrable sur toute cible. Son architecture est
            # exp(GLM_gelé(x) + offset·log(exposition)) : un modèle de COMPTAGE.
            # Sur une cible de SÉVÉRITÉ (coût par sinistre), l'offset d'exposition
            # est faux — le coût d'un sinistre ne dépend pas de la durée
            # d'observation. L'appelant l'exclut alors via modeles=('tabnet',).
            # TabNet, réseau tabulaire générique, n'a pas cette contrainte.
            res_cann = {}
            if 'cann' in modeles:
                logger.info(f"[{audit_id}] Calibration CANN ({n_epochs} époques)")
                res_cann = self._calibrer_cann(
                    X_train, X_test, y_train, y_test,
                    feature_names, device, n_epochs, batch_size, learning_rate,
                    result_a3=result_a3,
                    expo_train=expo_train, expo_test=expo_test,
                    X_val=X_val, y_val=y_val, expo_val=expo_val,
                )
                self.modeles['cann']   = res_cann['modele']
                self.metriques['cann'] = res_cann['metriques']
                rapport['etapes'].append('cann')
                logger.info(
                    f"CANN | Gini={res_cann['metriques']['gini_test']:.4f} | "
                    f"RMSE={res_cann['metriques']['rmse_test']:.2f}"
                )
            else:
                logger.info(
                    f"[{audit_id}] CANN NON calibré : exclu par l'appelant "
                    f"(modeles={modeles}) — son offset log(exposition) est une "
                    f"construction de modèle de comptage, incompatible avec la "
                    f"cible '{col_cible}'.")
                rapport['alertes'].append(
                    f"CANN non calibré : exclu pour la cible '{col_cible}' "
                    f"(offset log-exposition incompatible).")

            # ── TABNET ────────────────────────────────────────────────────────
            logger.info(f"[{audit_id}] Calibration TabNet ({n_epochs} époques)")
            res_tabnet = self._calibrer_tabnet(
                X_train, X_test, y_train, y_test,
                feature_names, device, n_epochs, batch_size, learning_rate,
                X_val=X_val, y_val=y_val,
            )
            self.modeles['tabnet']   = res_tabnet['modele']
            self.metriques['tabnet'] = res_tabnet['metriques']
            rapport['etapes'].append('tabnet')
            logger.info(
                f"TabNet | Gini={res_tabnet['metriques']['gini_test']:.4f} | "
                f"RMSE={res_tabnet['metriques']['rmse_test']:.2f}"
            )

            # ── CLASSEMENT ────────────────────────────────────────────────────
            classement = self._classer_modeles(result_a3, result_a4)
            rapport['etapes'].append('classement')

            # ── FEATURE IMPORTANCE TABNET ─────────────────────────────────────
            importance_tabnet = {}
            if hasattr(res_tabnet['modele'], 'get_feature_importance'):
                # Passe un batch pour générer les poids d'attention
                X_sample = torch.FloatTensor(X_test[:100]).to(device)
                with torch.no_grad():
                    res_tabnet['modele'](X_sample)
                importance_tabnet = res_tabnet['modele'].get_feature_importance(
                    feature_names
                )
                importance_tabnet = dict(
                    sorted(importance_tabnet.items(),
                           key=lambda x: x[1], reverse=True)[:10]
                )

            # ── GRAPHIQUES v2 ────────────────────────────────────────────────────
            graphiques = {}
            if generer_graphiques and PLOTLY_OK:
                logger.info(f"[{audit_id}] Graphiques PowerBI...")
                graphiques = self._generer_graphiques(
                    res_cann, res_tabnet, classement,
                    result_a3, result_a4, importance_tabnet
                )

            # ── RAPPORT ───────────────────────────────────────────────────────
            statut_rag  = self._calculer_statut_rag(classement)
            commentaire = self._commenter_actuaire_senior(
                classement, sous_branche, statut_rag,
                res_cann, res_tabnet, result_a3, result_a4
            )

            self._sauvegarder_modeles(sous_branche)
            self._sauvegarder_audit(audit_id, sous_branche, rapport,
                                     statut_rag, t_debut)

            if self.verbose:
                self._afficher_rapport_console(
                    audit_id, sous_branche, classement,
                    statut_rag, commentaire
                )

            # ── CALCUL VALIDATION DL ──────────────────────────────────────────
            _val_dl_ = self._valider_hypotheses_dl(
                classement, self.metriques,
                n_epochs if 'n_epochs' in dir() else 50,
                result_a3=result_a3,
                historiques={
                    'cann':   res_cann.get('historique', []),
                    'tabnet': res_tabnet.get('historique', []),
                })
            _gv_dl_  = self._graphiques_validation_dl(
                _val_dl_, classement, self.metriques) if generer_graphiques else {}

            # ── Standard ActuarIA — excel_bytes (audit V7 MINEUR #2) ──────────
            # A5 était le seul agent sans export Excel. Même pattern défensif
            # que les autres agents : échec de l'export n'interrompt jamais
            # le pipeline (log warning, excel_bytes reste b'').
            _excel_a5 = b''
            if TARIF_EXCEL_OK_A5:
                try:
                    _tmp_a5 = {
                        'success': True, 'statut_rag': statut_rag,
                        'classement': classement, 'branche': sous_branche,
                        'metriques': self.metriques, 'validation_dl': _val_dl_,
                        'audit_id': audit_id,
                    }
                    _excel_a5 = export_excel_a5(_tmp_a5, audit_id)
                    if _excel_a5:
                        logger.info(f"[{audit_id}] Excel A5 : {len(_excel_a5):,} bytes")
                except Exception as e_xl5:
                    logger.warning(f"Excel A5 échoué : {e_xl5}")

            # ── ALERTE MODÈLE : CANN non ancré (glm_gele=False) ───────────────
            # Surfacée dans le RÉSULTAT, pas seulement en log (personne ne lit
            # les logs). Si le CANN a tourné sans GLM Tweedie d'A3, sa couche GLM
            # reste librement entraînable : ce n'est PAS un CANN Wüthrich, il
            # n'est pas interprétable (audit S2). A6 lit ce flag pour plafonner
            # le gate global (même logique que la recalibration infidèle).
            _alertes_modele = []
            _met_cann = self.metriques.get('cann', {})
            if 'gini_test' in _met_cann and not _met_cann.get('glm_gele', False):
                _alertes_modele.append({
                    'modele': 'CANN', 'severite': 'AMBRE',
                    'code': 'cann_glm_non_ancre',
                    'message': "CANN NON ancre (glm_gele=False) : couche GLM "
                               "librement entrainable, ce n'est pas un CANN "
                               "Wuthrich, non interpretable (audit S2). Cause : "
                               "GLM Tweedie (A3) absent/indisponible.",
                })

            # ── MODÈLE AMPUTÉ → PLAFOND AMBRE (cf. A3/A4, même source unique) ─
            # Indépendant, par conception, du plafond d'ancrage CANN ci-dessus :
            # un CANN parfaitement ancré peut être amputé, et inversement. Les
            # deux alertes coexistent alors — aucune ne blanchit l'autre.
            _ampute = verifier_completude_plan(plan, df.columns)
            _al_amp = alerte_modele_ampute(_ampute, 'DL')
            if _al_amp:
                _alertes_modele.append(_al_amp)
                logger.warning("[PLAN INCOMPLET] %s", _al_amp['message'])
            statut_rag = plafonner_statut_si_ampute(statut_rag, _ampute)

            return {
                'success':             True,
                # Exclusions de conformité tracées par MatriceX (audit V11 / I5) :
                # une exclusion silencieuse est un défaut en soi — c'est ce silence
                # qui a rendu le BLOQUANT B5 si coûteux (facteur central de la RC Pro
                # détruit, −17,4 % de Gini, sans que rien ne l'indique nulle part).
                'exclusions_conformite': getattr(self, 'exclusions_conformite', {}),
                'controle_effet': getattr(self, 'controle_effet',
                                          {'execute': False, 'motifs': {}}),
                'alertes_conformite': getattr(self, 'alertes_conformite', {}),
                'alertes_modele':      _alertes_modele,
                'modele_ampute':       _ampute,
                'dataframe':           df,
                'branche':             sous_branche,
                'col_cible':           col_cible,   # cible sur laquelle CES modeles DL sont ajustes (A6 filtre dessus)
                'statut_rag':          statut_rag,
                'modeles':             self.modeles,
                'metriques':           self.metriques,
                'classement':          classement,
                'importance_tabnet':   importance_tabnet,
                'graphiques':            graphiques,
                'validation_dl':         _val_dl_,
                'graphiques_validation': _gv_dl_,
                'rapport':             rapport,
                'commentaire':         commentaire,
                'audit_id':            audit_id,
                'erreur':              None,
                'historique_cann':     res_cann.get('historique', []),
                'historique_tabnet':   res_tabnet.get('historique', []),
                'excel_bytes':         _excel_a5,
            }

        except Exception as e:
            logger.error(f"[{audit_id}] ERREUR : {e}", exc_info=True)
            return self._erreur(str(e), audit_id)

    # ══════════════════════════════════════════════════════════════════════════
    # PRÉPARATION DES DONNÉES
    # ══════════════════════════════════════════════════════════════════════════

    def _preparer_donnees(
        self,
        df:           pd.DataFrame,
        sous_branche: str,
        col_cible:    str,
        col_expo:     str,
        plan:         PlanTarifaire,
    ) -> Tuple:
        """
        Prépare et normalise les données pour PyTorch.

        NORMALISATION :
        ────────────────
        Les réseaux de neurones sont très sensibles à l'échelle des données.
        Un bonus-malus de 1.5 et un kilométrage de 15000 sur la même couche
        → le réseau donnerait beaucoup plus de poids au kilométrage.
        StandardScaler centre (moyenne=0) et réduit (std=1) chaque feature.

        Contrairement aux modèles tree-based (A4), la normalisation est
        OBLIGATOIRE pour les réseaux de neurones.

        EXPOSITION (audit V4) :
        ─────────────────────────
        L'exposition brute (train/test) est retournée séparément — elle
        sert à construire l'offset log(exposition) du CANN, à l'identique
        du GLM Tweedie d'A3 (offset additif, PAS une feature entraînable).
        """
        if col_cible not in df.columns:
            raise ValueError(f"Variable cible '{col_cible}' introuvable.")

        # Exclusion des colonnes non pertinentes
        cols_exclure = set(COLS_A_EXCLURE)
        cols_exclure.update(
            c for c in df.columns
            if any(mot in c for mot in COLS_CONTAMINEES)
        )
        cols_object = df.select_dtypes(include=['object']).columns.tolist()
        cols_exclure.update(cols_object)

        feature_names = [
            c for c in df.columns
            if c not in cols_exclure
            and c != col_cible
            and df[c].dtype in ['int64', 'float64', 'int32', 'float32']
            and df[c].isnull().sum() == 0
            and df[c].std() > 0
        ]

        # ── FILTRE GENRE (audit V7 BLOQUANT #1) ───────────────────────────────
        # A5 n'avait auparavant AUCUNE exclusion des variables de genre —
        # même trou que celui corrigé dans A4. Une colonne 'sexe' numérique
        # (0/1) ou pré-encodée ('sexe_enc') pouvait donc atteindre la
        # matrice X du CANN/TabNet. Réf. : Arrêt CJUE C-236/09 (Test-Achats).
        # ── MATRICE X CONFORME (immuable) — voir A4 pour le détail ────────────
        _mx = construire_matrice_x(
            feature_names, plan=plan,   # Phase 1 : liste blanche = plan.colonnes_produites()
            contexte='A5 — sélection features DL', logger_agent=logger,
            df=df, col_cible=col_cible,   # garde-fou n°4 : contrôle par l'EFFET
        )
        self.exclusions_conformite = _mx.exclusions
        # ⚠️ LE CONTRÔLE PAR L'EFFET VOYAGE AVEC SON MOTIF — `conformite/C7`.
        # La propriété existait depuis l'audit V14 avec la mention « À
        # REMONTER DANS LES RAPPORTS » ; mesuré, aucun agent ne la lisait.
        self.controle_effet = {'execute': _mx.controle_effet_execute,
                               'motifs': _mx.motifs_controle_effet}
        self.alertes_conformite = _mx.alertes
        feature_names = list(_mx)

        # ── SPLIT TEMPOREL (R1) ──────────────────────────────────────────────
        # Même approche que A3/A4 : tri temporel avant extraction de X.
        _col_temp = next(
            (c for c in ['annee_souscription', 'date_souscription', 'annee', 'year']
             if c in df.columns),
            None
        )
        if _col_temp is not None:
            df = df.sort_values(_col_temp).reset_index(drop=True)

        X = df[feature_names].fillna(0).values
        y = df[col_cible].values.astype(np.float32)
        expo = np.maximum(
            df.get(col_expo, pd.Series(np.ones(len(df)))).values.astype(np.float32),
            1e-6
        )

        # ── TROIS JEUX, ET PAS DEUX ──────────────────────────────────────────
        # ⚠️⚠️ CORRECTIF DU LOT 1.1 — constat `a5/C6`. Avant : il n'existait
        # que TRAIN et TEST, et l'early stopping choisissait `best_state` sur
        # la perte calculée **sur le TEST**. Le Gini test publié était donc le
        # MAXIMUM sur les époques, pas une estimation hors échantillon — et le
        # module citait pourtant Kaufman et al. (2012) sur la fuite, qu'il
        # évitait correctement pour le scaler et pas pour l'arrêt.
        #
        # Désormais : 80/20 train+val / test, puis 85/15 à l'intérieur du
        # premier — soit **68 % train · 12 % validation · 20 % test**. La
        # validation est découpée AVANT le scaler, comme le test, pour la même
        # raison et la même référence.
        if _col_temp is not None:
            n_tv = int(len(X) * 0.80)
            X_raw_tv, X_raw_test = X[:n_tv],    X[n_tv:]
            y_tv,     y_test     = y[:n_tv],    y[n_tv:]
            expo_tv,  expo_test  = expo[:n_tv], expo[n_tv:]
            # Coupure TEMPORELLE aussi pour la validation : la valider sur un
            # tirage aléatoire du passé alors que le test est le futur ferait
            # arrêter l'entraînement sur un régime que le test ne partage pas.
            n_fit = int(len(X_raw_tv) * 0.85)
            X_raw_train, X_raw_val = X_raw_tv[:n_fit], X_raw_tv[n_fit:]
            y_train,     y_val     = y_tv[:n_fit],     y_tv[n_fit:]
            expo_train,  expo_val  = expo_tv[:n_fit],  expo_tv[n_fit:]
        else:
            X_raw_tv, X_raw_test, y_tv, y_test, expo_tv, expo_test = \
                train_test_split(
                    X, y, expo, test_size=0.20, random_state=42
                )
            X_raw_train, X_raw_val, y_train, y_val, expo_train, expo_val = \
                train_test_split(
                    X_raw_tv, y_tv, expo_tv, test_size=0.15, random_state=42
                )

        # ⚠️ UNE VALIDATION TROP PETITE NE SE TAIT PAS. Sous ce seuil, l'arrêt
        # anticipé se règle sur du bruit — on le DIT plutôt que de revenir en
        # silence au test, ce qui rétablirait la fuite qu'on vient de fermer.
        if len(X_raw_val) < 30:
            logger.warning(
                f"[A5] Jeu de VALIDATION de {len(X_raw_val)} ligne(s) : "
                f"l'early stopping s'y règle sur du bruit. Le calibrage reste "
                f"honnête (aucune fuite du test), mais l'arrêt anticipé n'est "
                f"pas fiable sur un portefeuille de cette taille."
            )

        # Normalisation StandardScaler — ajusté sur TRAIN seul, appliqué au
        # reste. Réf. : Kaufman et al. (2012), ACM TKDD 6(4) — «Leakage in
        # Data Mining». La validation est traitée comme le test : elle ne
        # participe PAS à l'ajustement du scaler.
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_raw_train).astype(np.float32)
        X_val   = scaler.transform(X_raw_val).astype(np.float32)
        X_test  = scaler.transform(X_raw_test).astype(np.float32)
        self.scalers['standard'] = scaler

        return (X_train, X_val, X_test, y_train, y_val, y_test, feature_names,
                expo_train, expo_val, expo_test)


    # ══════════════════════════════════════════════════════════════════════════
    # CALIBRATION CANN
    # ══════════════════════════════════════════════════════════════════════════

    def _calibrer_cann(
        self,
        X_train: np.ndarray,
        X_test:  np.ndarray,
        y_train: np.ndarray,
        y_test:  np.ndarray,
        feature_names: List[str],
        device:  torch.device,
        n_epochs: int,
        batch_size: int,
        lr: float,
        result_a3:   Optional[Dict] = None,  # GLM Tweedie calibré par A3 (Wüthrich)
        expo_train:  Optional[np.ndarray] = None,
        expo_test:   Optional[np.ndarray] = None,
        # ⚠️ LOT 1.1 — l'early stopping se règle sur CES jeux, jamais sur le
        # test (constat `a5/C6`). Voir `_preparer_donnees`.
        X_val:       np.ndarray | None = None,
        y_val:       np.ndarray | None = None,
        expo_val:    np.ndarray | None = None,
    ) -> Dict:
        """
        Calibre le CANN (Combined Actuarial Neural Network).

        FONCTION DE PERTE :
        ────────────────────
        On utilise la Poisson Deviance comme fonction de perte.
        L(y, ŷ) = 2 × Σ [y×log(y/ŷ) - (y-ŷ)]

        Justification : la déviance Poisson est la métrique naturelle
        pour les données de comptage et les primes pures (toujours ≥ 0).
        Elle pénalise davantage les sous-estimations que les sur-estimations,
        ce qui est prudent du point de vue actuariel.

        EARLY STOPPING :
        ─────────────────
        On arrête l'entraînement si la perte de validation ne diminue
        pas pendant 10 époques consécutives.
        Justification : évite l'overfitting sans fixer le nombre d'époques
        de façon arbitraire.

        GEL DU GLM (audit V4 — correction de l'implémentation précédente) :
        ─────────────────────────────────────────────────────────────────────
        La correction précédente initialisait `glm_layer` depuis le GLM
        Poisson d'A3, SANS geler la couche (elle continuait à s'entraîner
        librement) ET sans corriger l'échelle (les coefficients GLM sont
        calibrés sur variables BRUTES, alors que le CANN reçoit des
        variables STANDARDISÉES — mélanger les deux rend l'initialisation
        incorrecte dès l'époque 0). L'offset d'exposition était par
        ailleurs totalement absent.

        Cette version corrige les 4 points :
        1. Utilise le GLM TWEEDIE (pas Poisson) — c'est le modèle qui prédit
           directement la prime pure, la cible réelle du CANN.
        2. Reprojette les coefficients bruts du GLM vers l'échelle
           standardisée : pour x_brut = x_std × σ + μ,
           β_brut × x_brut = (β_brut × σ) × x_std + (β_brut × μ)
           → poids_std = β_brut × σ ; le terme (β_brut × μ) est absorbé
           dans l'intercept.
        3. GÈLE la couche GLM (`requires_grad=False`, fait dans
           `CANNModel.__init__`) — elle ne bouge plus jamais pendant
           l'entraînement. Les coefficients extractibles à tout moment
           restent identiques au GLM Tweedie audité par A3.
        4. Calcule et transmet l'offset log(exposition) à `forward()`,
           à l'identique de la sémantique statsmodels.

        Une vérification numérique est effectuée juste après la
        construction du modèle : la prédiction du CANN à l'époque 0
        (avant tout entraînement) est comparée à la prédiction du GLM
        Tweedie seul — l'écart doit être quasi nul (résiduel non entraîné
        = 0 par construction). Cet écart est journalisé et exposé dans
        les métriques (`glm_verification_error`) pour traçabilité.

        Réf. : Wüthrich & Merz (2019), "Editorial: Yes, we CANN!",
               ASTIN Bulletin 49(1).
        """
        # ⚠️⚠️ LE JEU DE VALIDATION EST EXIGE, JAMAIS DEDUIT. Un repli
        # silencieux -- « si X_val est absent, on valide sur le test » --
        # rouvrirait exactement la fuite que le lot 1.1 ferme (constat
        # `a5/C6`), et il le ferait SANS QUE PERSONNE NE LE VOIE. Le depot
        # applique deja cette regle a `col_cible` : un defaut que personne
        # n'utilise et qui contredit la methode est un piege, pas une
        # commodite.
        if X_val is None or y_val is None:
            raise ValueError(
                "_calibrer_cann exige X_val et y_val : l'arret anticipe se regle sur un "
                "jeu de VALIDATION distinct, jamais sur le test. Les trois jeux "
                "sont produits par _preparer_donnees (68 / 12 / 20)."
            )

        n_features = X_train.shape[1]

        # ── Construction offset (log-exposition), séparé des features ────────
        if expo_train is not None and expo_test is not None:
            offset_train_np = np.log(np.maximum(expo_train, 1e-6)).astype(np.float32)
            offset_test_np  = np.log(np.maximum(expo_test,  1e-6)).astype(np.float32)
        else:
            offset_train_np = np.zeros(len(X_train), dtype=np.float32)
            offset_test_np  = np.zeros(len(X_test),  dtype=np.float32)

        # ── GEL DU GLM TWEEDIE D'A3 (Wüthrich & Merz 2019) ────────────────────
        w_init, bias_init = None, None
        glm_ref_info = {'glm_gele': False, 'n_vars_glm_total': 0, 'n_vars_glm_matchees': 0}

        if result_a3 and result_a3.get('success'):
            try:
                modele_glm = result_a3.get('modeles', {}).get('tweedie')
                scaler_std = self.scalers.get('standard')
                if (modele_glm is not None and hasattr(modele_glm, 'params')
                        and scaler_std is not None):
                    params_glm  = modele_glm.params
                    vars_glm    = [v for v in params_glm.index if v != 'const']
                    glm_ref_info['n_vars_glm_total'] = len(vars_glm)

                    w_init_local    = np.zeros(n_features, dtype=np.float32)
                    bias_shift      = 0.0
                    vars_matchees   = []
                    vars_non_matchees = []

                    for var in vars_glm:
                        if var in feature_names:
                            j        = feature_names.index(var)
                            beta_brut = float(params_glm[var])
                            sigma_j   = float(scaler_std.scale_[j])
                            mu_j      = float(scaler_std.mean_[j])
                            # Reprojection échelle standardisée (voir docstring)
                            w_init_local[j] = beta_brut * sigma_j
                            bias_shift     += beta_brut * mu_j
                            vars_matchees.append(var)
                        else:
                            vars_non_matchees.append(var)

                    intercept_glm = float(params_glm.get('const', 0.0))
                    bias_init_local = intercept_glm + bias_shift

                    glm_ref_info['n_vars_glm_matchees'] = len(vars_matchees)
                    if vars_non_matchees:
                        logger.warning(
                            f"[CANN] {len(vars_non_matchees)} variable(s) du GLM "
                            f"Tweedie absente(s) des features CANN — reproduction "
                            f"du GLM partielle pour : {vars_non_matchees}. "
                            f"Le CANN gelé n'inclura PAS l'effet de ces variables."
                        )

                    w_init, bias_init = w_init_local, bias_init_local
                    logger.info(
                        f"[CANN] Coefficients GLM Tweedie prêts au gel | "
                        f"{len(vars_matchees)}/{len(vars_glm)} variable(s) "
                        f"appariée(s) | intercept_glm={intercept_glm:.4f}"
                    )
                elif modele_glm is None:
                    logger.warning(
                        "[CANN] GLM Tweedie (A3) indisponible — le CANN ne "
                        "sera PAS un vrai CANN Wüthrich (couche GLM librement "
                        "entraînable, non interprétable pour l'audit S2)."
                    )
            except Exception as e_init:
                logger.warning(f"[CANN] Préparation du gel GLM échouée : {e_init}")
        else:
            logger.warning(
                "[CANN] result_a3 non fourni — le CANN ne sera PAS un vrai "
                "CANN Wüthrich (couche GLM librement entraînable)."
            )

        # ── Modèle — GLM gelé si w_init/bias_init disponibles ─────────────────
        modele = CANNModel(
            n_features      = n_features,
            hidden_sizes    = [64, 32],
            glm_weight_init = w_init,
            glm_bias_init   = bias_init,
        ).to(device)
        glm_ref_info['glm_gele'] = modele.glm_gele

        # ── VÉRIFICATION NUMÉRIQUE — CANN(epoch 0) == GLM seul ────────────────
        # Si le GLM est gelé et le résiduel initialisé à zéro, la prédiction
        # du CANN à l'instant zéro DOIT être quasi identique à la prédiction
        # du GLM Tweedie seul (aux erreurs d'arrondi flottant près).
        glm_verification_error = None
        if modele.glm_gele:
            modele.eval()
            with torch.no_grad():
                offset_test_t = torch.FloatTensor(offset_test_np).to(device)
                pred_cann_epoch0 = modele(
                    torch.FloatTensor(X_test).to(device), offset_test_t
                ).cpu().numpy()
            # Prédiction GLM "manuelle" équivalente : exp(w·x_std + bias + offset)
            pred_glm_manuel = np.exp(
                X_test @ w_init + bias_init + offset_test_np
            )
            ecart_relatif = np.abs(
                (pred_cann_epoch0 - pred_glm_manuel) /
                np.maximum(np.abs(pred_glm_manuel), 1e-6)
            )
            glm_verification_error = float(np.max(ecart_relatif))
            if glm_verification_error < 1e-3:
                logger.info(
                    f"[CANN] ✓ Vérification GLM gelé OK — écart max "
                    f"{glm_verification_error:.2e} (CANN époque 0 ≡ GLM Tweedie)"
                )
            else:
                logger.warning(
                    f"[CANN] ⚠ Écart CANN/GLM à l'époque 0 = "
                    f"{glm_verification_error:.4f} — vérifier la reprojection "
                    f"d'échelle (attendu < 1e-3)."
                )
            modele.train()

        # Optimizer Adam — uniquement les paramètres NON gelés
        # (filter() exclut glm_layer si glm_gele=True — le GLM ne reçoit
        # jamais de mise à jour, il reste identique au GLM Tweedie audité)
        parametres_entrainables = filter(lambda p: p.requires_grad, modele.parameters())
        optimizer = optim.Adam(
            parametres_entrainables,
            lr           = lr,
            weight_decay = 1e-4
        )

        # Learning rate scheduler — réduit lr si plateau
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=5
        )

        # DataLoader — inclut l'offset comme 3e tenseur
        train_ds     = TensorDataset(
            torch.FloatTensor(X_train).to(device),
            torch.FloatTensor(y_train).to(device),
            torch.FloatTensor(offset_train_np).to(device),
        )
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

        # ⚠️ `y_test` N'EST VOLONTAIREMENT PAS TENSORISE : plus aucune ligne de
        # cette fonction n'a besoin de lire la CIBLE du test. Ne pas le
        # recreer -- c'est par ce tenseur que la fuite `a5/C6` passait.
        X_test_t      = torch.FloatTensor(X_test).to(device)
        offset_test_t = torch.FloatTensor(offset_test_np).to(device)

        # ⚠️⚠️ L'ARRET ANTICIPE SE REGLE SUR LA VALIDATION, JAMAIS SUR LE TEST
        # (constat `a5/C6`). Ces trois tenseurs sont ceux que la boucle lit
        # pour choisir `best_state` ; `X_test_t` ne sert plus qu'a la mesure
        # FINALE, une seule fois, apres l'entrainement.
        offset_val_np = (np.log(np.maximum(expo_val, 1e-6)).astype(np.float32)
                         if (expo_val is not None and offset_train_np.any())
                         else np.zeros(len(X_val), dtype=np.float32))
        X_val_t      = torch.FloatTensor(X_val).to(device)
        y_val_t      = torch.FloatTensor(y_val).to(device)
        offset_val_t = torch.FloatTensor(offset_val_np).to(device)

        # Entraînement avec early stopping
        best_val_loss = float('inf')
        patience_cnt  = 0
        patience_max  = 10
        historique    = []

        modele.train()
        for epoch in range(n_epochs):
            # ── TRAIN ─────────────────────────────────────────────────────────
            train_loss = 0.0
            for X_batch, y_batch, offset_batch in train_loader:
                optimizer.zero_grad()
                pred = modele(X_batch, offset_batch)
                # Poisson deviance loss
                pred_pos = torch.clamp(pred, min=1e-7)
                y_pos    = torch.clamp(y_batch, min=1e-7)
                loss     = torch.mean(
                    2 * (y_pos * torch.log(y_pos / pred_pos) - (y_pos - pred_pos))
                )
                loss.backward()
                # Gradient clipping — évite l'explosion des gradients
                nn.utils.clip_grad_norm_(
                    filter(lambda p: p.requires_grad, modele.parameters()),
                    max_norm=1.0
                )
                optimizer.step()
                train_loss += loss.item()

            train_loss /= len(train_loader)

            # ── VALIDATION ────────────────────────────────────────────────────
            modele.eval()
            with torch.no_grad():
                pred_val = modele(X_val_t, offset_val_t)
                pred_pos = torch.clamp(pred_val, min=1e-7)
                y_pos    = torch.clamp(y_val_t, min=1e-7)
                val_loss = torch.mean(
                    2 * (y_pos * torch.log(y_pos / pred_pos) - (y_pos - pred_pos))
                ).item()
            modele.train()

            scheduler.step(val_loss)
            historique.append({'epoch': epoch+1, 'train': train_loss, 'val': val_loss})

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_cnt  = 0
                # Sauvegarde du meilleur état
                best_state = {k: v.clone() for k, v in modele.state_dict().items()}
            else:
                patience_cnt += 1
                if patience_cnt >= patience_max:
                    logger.info(f"CANN Early stopping à l'époque {epoch+1}")
                    break

            if (epoch + 1) % 10 == 0:
                logger.info(
                    f"  CANN Époque {epoch+1}/{n_epochs} | "
                    f"Train={train_loss:.4f} | Val={val_loss:.4f}"
                )

        # Rechargement du meilleur état
        if 'best_state' in locals():
            modele.load_state_dict(best_state)

        # Métriques finales
        modele.eval()
        with torch.no_grad():
            pred_test  = modele(X_test_t, offset_test_t).cpu().numpy()
            offset_train_t = torch.FloatTensor(offset_train_np).to(device)
            pred_train = modele(
                torch.FloatTensor(X_train).to(device), offset_train_t
            ).cpu().numpy()

        metriques = self._calculer_metriques(
            y_train, y_test, pred_train, pred_test, 'cann'
        )
        metriques['n_epochs_reels'] = len(historique)
        metriques['best_val_loss']  = round(best_val_loss, 4)
        # Traçabilité de l'interprétabilité réelle du modèle (audit V4)
        metriques['glm_gele']              = glm_ref_info['glm_gele']
        metriques['n_vars_glm_total']       = glm_ref_info['n_vars_glm_total']
        metriques['n_vars_glm_matchees']    = glm_ref_info['n_vars_glm_matchees']
        metriques['glm_verification_error'] = (
            round(glm_verification_error, 6)
            if glm_verification_error is not None else None
        )

        return {'modele': modele, 'metriques': metriques, 'historique': historique}


    # ══════════════════════════════════════════════════════════════════════════
    # CALIBRATION TABNET
    # ══════════════════════════════════════════════════════════════════════════

    def _calibrer_tabnet(
        self,
        X_train: np.ndarray,
        X_test:  np.ndarray,
        y_train: np.ndarray,
        y_test:  np.ndarray,
        feature_names: List[str],
        device:  torch.device,
        n_epochs: int,
        batch_size: int,
        lr: float,
        # ⚠️ LOT 1.1 — l'early stopping se règle sur CE jeu, jamais sur le
        # test (constat `a5/C6`). Voir `_preparer_donnees`.
        X_val: np.ndarray | None = None,
        y_val: np.ndarray | None = None,
    ) -> Dict:
        """
        Calibre TabNet avec mécanisme d'attention séquentielle.
        Même logique d'entraînement que CANN.
        """
        # ⚠️⚠️ LE JEU DE VALIDATION EST EXIGE, JAMAIS DEDUIT. Un repli
        # silencieux -- « si X_val est absent, on valide sur le test » --
        # rouvrirait exactement la fuite que le lot 1.1 ferme (constat
        # `a5/C6`), et il le ferait SANS QUE PERSONNE NE LE VOIE. Le depot
        # applique deja cette regle a `col_cible` : un defaut que personne
        # n'utilise et qui contredit la methode est un piege, pas une
        # commodite.
        if X_val is None or y_val is None:
            raise ValueError(
                "_calibrer_tabnet exige X_val et y_val : l'arret anticipe se regle sur un "
                "jeu de VALIDATION distinct, jamais sur le test. Les trois jeux "
                "sont produits par _preparer_donnees (68 / 12 / 20)."
            )

        n_features = X_train.shape[1]

        modele = TabNetSimple(
            n_features  = n_features,
            n_steps     = 3,
            hidden_size = 64,
        ).to(device)

        optimizer = optim.Adam(
            modele.parameters(),
            lr           = lr,
            weight_decay = 1e-4
        )
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=5
        )

        train_ds     = TensorDataset(
            torch.FloatTensor(X_train).to(device),
            torch.FloatTensor(y_train).to(device)
        )
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

        # ⚠️ `y_test` n'est volontairement pas tensorise -- voir `_calibrer_cann`.
        X_test_t = torch.FloatTensor(X_test).to(device)

        # ⚠️⚠️ L'ARRET ANTICIPE SE REGLE SUR LA VALIDATION, JAMAIS SUR LE TEST
        # (constat `a5/C6`) -- meme correctif que le CANN. `X_test_t` ne sert
        # plus qu'a la mesure FINALE, apres l'entrainement.
        X_val_t = torch.FloatTensor(X_val).to(device)
        y_val_t = torch.FloatTensor(y_val).to(device)

        best_val_loss = float('inf')
        patience_cnt  = 0
        patience_max  = 10
        historique    = []

        modele.train()
        for epoch in range(n_epochs):
            train_loss = 0.0
            for X_batch, y_batch in train_loader:
                optimizer.zero_grad()
                pred     = modele(X_batch)
                pred_pos = torch.clamp(pred, min=1e-7)
                y_pos    = torch.clamp(y_batch, min=1e-7)
                loss     = torch.mean(
                    2 * (y_pos * torch.log(y_pos / pred_pos) - (y_pos - pred_pos))
                )
                loss.backward()
                nn.utils.clip_grad_norm_(modele.parameters(), max_norm=1.0)
                optimizer.step()
                train_loss += loss.item()

            train_loss /= len(train_loader)

            modele.eval()
            with torch.no_grad():
                pred_val = modele(X_val_t)
                pred_pos = torch.clamp(pred_val, min=1e-7)
                y_pos    = torch.clamp(y_val_t, min=1e-7)
                val_loss = torch.mean(
                    2 * (y_pos * torch.log(y_pos / pred_pos) - (y_pos - pred_pos))
                ).item()
            modele.train()

            scheduler.step(val_loss)
            historique.append({'epoch': epoch+1, 'train': train_loss, 'val': val_loss})

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_cnt  = 0
                best_state    = {k: v.clone() for k, v in modele.state_dict().items()}
            else:
                patience_cnt += 1
                if patience_cnt >= patience_max:
                    logger.info(f"TabNet Early stopping à l'époque {epoch+1}")
                    break

            if (epoch + 1) % 10 == 0:
                logger.info(
                    f"  TabNet Époque {epoch+1}/{n_epochs} | "
                    f"Train={train_loss:.4f} | Val={val_loss:.4f}"
                )

        if 'best_state' in locals():
            modele.load_state_dict(best_state)

        modele.eval()
        with torch.no_grad():
            pred_test  = modele(X_test_t).cpu().numpy()
            pred_train = modele(
                torch.FloatTensor(X_train).to(device)
            ).cpu().numpy()

        metriques = self._calculer_metriques(
            y_train, y_test, pred_train, pred_test, 'tabnet'
        )
        metriques['n_epochs_reels'] = len(historique)
        metriques['best_val_loss']  = round(best_val_loss, 4)

        return {'modele': modele, 'metriques': metriques, 'historique': historique}

    # ══════════════════════════════════════════════════════════════════════════
    # MÉTRIQUES
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_metriques(
        self,
        y_train:    np.ndarray,
        y_test:     np.ndarray,
        pred_train: np.ndarray,
        pred_test:  np.ndarray,
        nom:        str
    ) -> Dict:
        """Calcule les métriques de performance.

        ⚠️⚠️ LA BASE DU GINI DIFFÈRE ENTRE LES DEUX MODÈLES D'A5, ET C'EST
        MESURÉ (constat `a4/C10`, élargi le 27/08/2026) :
          · CANN   — `modele(X_test_t, offset_test_t)` : l'offset log(exposition)
            est appliqué dans le `forward`, donc le tri porte sur un COMPTAGE ;
          · TabNet — `modele(X_test_t)` : aucun offset, tri UNITAIRE.
        **A5 compare donc déjà deux bases entre ses propres modèles.** On ne
        corrige pas ici — aligner changerait un Gini publié, donc le modèle
        retenu, donc un prix. On DÉCLARE.
        """
        gini_train = self._calculer_gini(y_train, pred_train)
        gini_test  = self._calculer_gini(y_test,  pred_test)
        overfit    = gini_train / max(gini_test, 1e-6)
        rmse_test  = float(np.sqrt(mean_squared_error(y_test, pred_test)))

        return {
            'gini_train':    round(gini_train, 4),
            'gini_test':     round(gini_test,  4),
            # ⚠️ Base MESURÉE par modèle, jamais supposée — voir la docstring.
            'base_gini':     (BASE_GINI_COMPTAGE if nom == 'cann'
                              else BASE_GINI_UNITAIRE),
            'overfit_ratio': round(overfit,     3),
            'rmse_test':     round(rmse_test,   2),
            'pred_mean':     round(float(pred_test.mean()), 2),
            'obs_mean':      round(float(y_test.mean()),    2),
        }

    def _calculer_gini(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Gini décroissant — même méthode que A3/A4."""
        if len(y_true) == 0:
            return 0.0
        try:
            order   = np.argsort(y_pred)[::-1]
            y_true  = np.array(y_true)[order]
            n       = len(y_true)
            cum_obs = np.cumsum(y_true) / np.sum(y_true)
            cum_pop = np.arange(1, n+1) / n
            fn      = np.trapezoid if hasattr(np, 'trapezoid') else np.trapz
            auc     = fn(cum_obs, cum_pop)
            # ⚠ AUTO-AUDIT (11/07/2026) — NE PAS ÉCRÊTER LE GINI À ZÉRO.
            # L'écrêtage np.clip(gini, 0.0, 1.0) rendait INVISIBLE le cas le plus
            # dangereux qui soit en tarification : un Gini NÉGATIF, c'est-à-dire
            # un modèle ANTI-SÉLECTIF — il fait payer MOINS les mauvais risques.
            # Un Gini réel de −0,50 était rapporté « 0,0000 », donc indiscernable
            # d'un modèle simplement non discriminant. Or les deux situations
            # n'ont rien à voir : la seconde est inutile, la première est
            # ruineuse (anti-sélection = spirale de sélection adverse).
            # On rapporte désormais la valeur VRAIE, bornée à [−1, 1], et on
            # alerte explicitement en cas d'anti-sélection.
            gini = float(np.clip(2 * auc - 1, -1.0, 1.0))
            if gini < 0:
                logger.warning(
                    f"[ANTI-SÉLECTION] Gini NÉGATIF ({gini:.4f}) — le modèle "
                    f"discrimine À L'ENVERS : il attribue les primes les plus "
                    f"faibles aux risques les plus élevés. Modèle INUTILISABLE "
                    f"en l'état, quelle que soit sa performance par ailleurs."
                )
            return gini
        except Exception:
            return 0.0

    # ══════════════════════════════════════════════════════════════════════════
    # CLASSEMENT
    # ══════════════════════════════════════════════════════════════════════════

    def _classer_modeles(
        self,
        result_a3: Optional[Dict],
        result_a4: Optional[Dict]
    ) -> List[Dict]:
        """Classe CANN + TabNet + références A3/A4."""
        classement = []

        for nom, met in self.metriques.items():
            entree = {
                'modele':        nom.upper(),
                'gini_test':     met['gini_test'],
                'rmse_test':     met['rmse_test'],
                'overfit_ratio': met['overfit_ratio'],
                'type':          'Deep Learning',
            }
            # Traçabilité interprétabilité (audit V4) — uniquement pertinent
            # pour le CANN (TabNet n'a jamais prétendu à l'interprétabilité GLM).
            if nom == 'cann' and 'glm_gele' in met:
                entree['glm_gele'] = met['glm_gele']
                entree['glm_verification_error'] = met.get('glm_verification_error')
            classement.append(entree)

        # Meilleur ML de A4
        if result_a4 and result_a4.get('success'):
            cl_a4 = result_a4.get('classement', [])
            ml_only = [c for c in cl_a4 if 'GLM' not in c['modele']]
            if ml_only:
                best_ml = ml_only[0]
                classement.append({
                    'modele':        f"ML Best ({best_ml['modele']})",
                    'gini_test':     best_ml['gini_test'],
                    'rmse_test':     best_ml['rmse_test'],
                    'overfit_ratio': best_ml.get('overfit_ratio', 1.0),
                    'type':          'Référence A4',
                })

        # GLM A3
        if result_a3 and result_a3.get('success'):
            gini_glm = result_a3['metriques'].get('poisson', {}).get('gini', 0)
            classement.append({
                'modele':        'GLM Poisson (A3)',
                'gini_test':     gini_glm,
                'rmse_test':     result_a3['metriques'].get('poisson', {}).get('rmse_test', 0),
                'overfit_ratio': 1.0,
                'type':          'Référence A3',
            })

        classement.sort(key=lambda x: x['gini_test'], reverse=True)
        return classement

    # ══════════════════════════════════════════════════════════════════════════
    # SAUVEGARDE
    # ══════════════════════════════════════════════════════════════════════════

    def _sauvegarder_modeles(self, sous_branche: str) -> None:
        """Sauvegarde les modèles PyTorch sur Drive."""
        for nom, modele in self.modeles.items():
            chemin = self.models_path / f"dl_{nom}_{sous_branche}.pt"
            try:
                torch.save(modele.state_dict(), chemin)
                logger.info(f"Modèle {nom} sauvegardé : {chemin}")
            except Exception as e:
                logger.warning(f"Sauvegarde {nom} échouée : {e}")

        # Métriques JSON
        chemin_json = self.models_path / f"dl_metriques_{sous_branche}.json"
        try:
            with open(chemin_json, 'w') as f:
                json.dump({
                    'sous_branche': sous_branche,
                    'timestamp':    datetime.now().isoformat(),
                    'metriques':    self.metriques,
                }, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Métriques non sauvegardées : {e}")

    def _sauvegarder_audit(
        self, audit_id, sous_branche, rapport, statut_rag, t_debut
    ) -> None:
        log = {
            'audit_id':     audit_id,
            'agent':        'A5_DEEP_LEARNING',
            'timestamp':    t_debut.isoformat(),
            'sous_branche': sous_branche,
            'statut_rag':   statut_rag,
            'etapes':       rapport['etapes'],
        }
        try:
            with open(self.audit_path / f"{audit_id}.json", 'w') as f:
                json.dump(log, f, indent=2, default=str)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # STATUT RAG & COMMENTAIRES
    # ══════════════════════════════════════════════════════════════════════════

    def _calculer_statut_rag(self, classement: List[Dict]) -> str:
        dl_models = [c for c in classement if c.get('type') == 'Deep Learning']
        if not dl_models:
            return 'ROUGE'
        best_gini = max(m['gini_test'] for m in dl_models)
        if best_gini >= 0.15:
            return 'VERT'
        elif best_gini >= 0.05:
            return 'AMBRE'
        return 'ROUGE'

    def _commenter_actuaire_senior(
        self,
        classement:   List[Dict],
        sous_branche: str,
        statut_rag:   str,
        res_cann:     Dict,
        res_tabnet:   Dict,
        result_a3:    Optional[Dict],
        result_a4:    Optional[Dict]
    ) -> str:
        emoji  = glyphe_rag(statut_rag)
        # res_cann peut être VIDE : le CANN est exclu des cibles de sévérité
        # (offset log-exposition incompatible). On le DIT, on ne l'invente pas.
        m_cann = res_cann.get('metriques') or {}
        m_tab  = res_tabnet.get('metriques') or {}

        # Gini de référence
        gini_glm = 0
        gini_ml  = 0
        if result_a3 and result_a3.get('success'):
            gini_glm = result_a3['metriques'].get('poisson', {}).get('gini', 0)
        if result_a4 and result_a4.get('success'):
            ml_only = [c for c in result_a4.get('classement', [])
                       if 'GLM' not in c['modele']]
            if ml_only:
                gini_ml = ml_only[0]['gini_test']

        _l_cann = (
            f"CANN   : Gini={m_cann['gini_test']:.4f} | "
            f"RMSE={m_cann['rmse_test']:.2f} | "
            f"Époques={m_cann.get('n_epochs_reels', 'N/A')}\n"
            if m_cann else
            "CANN   : NON calibré — exclu de cette cible (son offset "
            "log(exposition) est une construction de modèle de comptage, "
            "incompatible avec la sévérité).\n"
        )
        n1 = (
            f"{emoji} DEEP LEARNING — {statut_rag}\n"
            f"Sous-branche : {sous_branche}\n\n"
            f"{_l_cann}"
            f"TabNet : Gini={m_tab['gini_test']:.4f} | "
            f"RMSE={m_tab['rmse_test']:.2f} | "
            f"Époques={m_tab.get('n_epochs_reels', 'N/A')}\n\n"
            f"Références :\n"
            f"  GLM Poisson (A3) : {gini_glm:.4f}\n"
            f"  Meilleur ML (A4) : {gini_ml:.4f}"
        )

        # Max sur les modèles RÉELLEMENT calibrés (le CANN peut être exclu).
        best_dl_gini = max([m['gini_test'] for m in (m_cann, m_tab) if m] or [0.0])

        if statut_rag == 'VERT':
            n2 = (
                "DIAGNOSTIC ACTUARIEL :\n"
                f"Les modèles Deep Learning atteignent un Gini de "
                f"{best_dl_gini:.4f}, comparable aux meilleurs modèles ML. "
                f"Le CANN présente l'avantage de conserver une composante GLM "
                f"interprétable, ce qui facilite la justification devant un "
                f"auditeur S2. TabNet fournit une importance des features "
                f"native via son mécanisme d'attention."
            )
            n3 = (
                "RECOMMANDATION :\n"
                "→ Comparer CANN vs meilleur ML (A4) en validation croisée.\n"
                "→ Passer à l'agent A6 (Comparaison finale).\n"
                "→ CANN recommandé si interprétabilité prioritaire.\n"
                "→ Meilleur ML (A4) recommandé si Gini prioritaire."
            )
        else:
            n2 = (
                "DIAGNOSTIC ACTUARIEL :\n"
                f"Le Gini des modèles DL ({best_dl_gini:.4f}) reste en dessous "
                f"des modèles ML. 50 époques sur CPU Colab peuvent être "
                f"insuffisantes pour que les réseaux convergent pleinement. "
                f"Augmenter n_epochs=100 sur Colab Pro GPU améliorerait les résultats."
            )
            n3 = (
                "RECOMMANDATION :\n"
                "→ Utiliser le meilleur ML (A4) comme modèle de production.\n"
                "→ CANN/TabNet : relancer avec n_epochs=100 sur Colab Pro.\n"
                "→ Passer à l'agent A6 pour la décision finale."
            )

        return f"{n1}\n\n{n2}\n\n{n3}"

    def _afficher_rapport_console(
        self, audit_id, sous_branche, classement, statut_rag, commentaire
    ) -> None:
        emoji = glyphe_rag(statut_rag)
        sep   = "═" * 65
        print(f"\n{sep}")
        print(f"  ACTUARIA — AGENT A5 DEEP LEARNING | {audit_id}")
        print(sep)
        print(f"  {emoji} STATUT : {statut_rag}")
        print(f"\n  {'Modèle':<35} {'Gini':<10} {'RMSE':<10} {'Type'}")
        print(f"  {'-'*60}")
        for c in classement:
            print(
                f"  {c['modele']:<35} "
                f"{c['gini_test']:<10.4f} "
                f"{c['rmse_test']:<10.2f} "
                f"{c.get('type','')}"
            )
        print(f"\n{sep}")
        for ligne in commentaire.split('\n'):
            print(f"  {ligne}")
        print(sep + "\n")

    # ══════════════════════════════════════════════════════════════════════════
    # GRAPHIQUES v2 — Style PowerBI/Bloomberg
    # ══════════════════════════════════════════════════════════════════════════

    def _generer_graphiques(
        self,
        res_cann:         Dict,
        res_tabnet:       Dict,
        classement:       List[Dict],
        result_a3:        Optional[Dict],
        result_a4:        Optional[Dict],
        importance_tabnet: Dict,
    ) -> Dict:
        """
        Génère 4 graphiques Deep Learning style PowerBI.

        G1 — Courbes d'apprentissage CANN (loss train vs val)
        G2 — Courbes d'apprentissage TabNet
        G3 — Comparaison Gini : DL vs ML vs GLM
        G4 — Feature Importance TabNet (attention)
        """
        if not PLOTLY_OK:
            return {}

        NAVY    = "#0F2E52"
        NAVY_L  = "#1B3A5C"
        NAVY_LL = "#243F6A"
        OR      = "#C9A84C"
        BLANC   = "#F0F4F8"
        GRIS    = "#8A9AB0"
        # ⚠️ Couleurs RAG lues à la SOURCE UNIQUE (`core/charts_tarif`), jamais
        # redéfinies : 30 définitions locales et 7 valeurs distinctes existaient.
        VERT = couleur_rag("VERT", FOND_SOMBRE)
        ROUGE = couleur_rag("ROUGE", FOND_SOMBRE)
        AMBRE = couleur_rag("AMBRE", FOND_SOMBRE)
        BLEU    = "#3498DB"

        LAYOUT_BASE = dict(
            paper_bgcolor = NAVY,
            plot_bgcolor  = NAVY_L,
            font          = dict(family="Inter, Arial", color=BLANC, size=11),
            margin        = dict(l=16, r=16, t=52, b=16),
            height        = 300,
            hoverlabel    = dict(bgcolor=NAVY_LL, bordercolor=OR,
                                 font_size=12, font_color=BLANC),
            legend        = dict(
                bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=10),
                orientation="h", yanchor="bottom", y=1.02,
            ),
        )

        graphiques = {}

        # ── G1 : COURBES D'APPRENTISSAGE CANN ────────────────────────────────
        try:
            hist_cann = res_cann.get('historique', [])
            if hist_cann:
                epochs     = list(range(1, len(hist_cann) + 1))
                # ⚠️ L'HISTORIQUE PORTE `train` ET `val`, PAS `loss_train` ni
                # `loss_val` : `_calibrer_cann` empile {'epoch','train','val'}.
                # Les listes sortaient donc à zéro sur toute leur longueur, et
                # la figure « Courbes d'apprentissage » montrait des droites
                # plates quelle que soit la calibration.
                # ⚠️ UN GINI PAR ÉPOQUE N'A JAMAIS ÉTÉ ENREGISTRÉ : la trace
                # « Gini Val » était une ligne de zéros, et la « Best époque »
                # qu'elle plaçait — index du maximum de ces zéros — valait
                # toujours 1. L'époque réellement retenue est celle que
                # l'early stopping restaure : le minimum de la perte de
                # validation. C'est elle qui est marquée ici.
                loss_train = [h.get('train', 0.0) for h in hist_cann]
                loss_val   = [h.get('val',   0.0) for h in hist_cann]

                fig1 = go.Figure()

                # Loss train
                fig1.add_trace(go.Scatter(
                    x=epochs, y=loss_train,
                    mode='lines', name='Loss Train',
                    line=dict(color=OR, width=2, shape='spline', smoothing=0.4),
                    hovertemplate="Époque %{x}<br>Loss Train : <b>%{y:.4f}</b><extra></extra>",
                ))

                # Loss val
                fig1.add_trace(go.Scatter(
                    x=epochs, y=loss_val,
                    mode='lines', name='Loss Val',
                    line=dict(color=ROUGE, width=2, shape='spline', smoothing=0.4, dash='dash'),
                    hovertemplate="Époque %{x}<br>Loss Val : <b>%{y:.4f}</b><extra></extra>",
                ))

                # Époque retenue = minimum de la perte de validation
                best_epoch = loss_val.index(min(loss_val)) + 1
                fig1.add_vline(
                    x=best_epoch, line_dash="dot", line_color=VERT, line_width=1.5,
                    annotation_text=f"Époque retenue {best_epoch}",
                    annotation_font=dict(color=VERT, size=9),
                )

                fig1.update_layout(
                    title=dict(text="📈 CANN — Courbes d'apprentissage",
                               font=dict(color=BLANC, size=13), x=0.01),
                    paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                    font=dict(family="Inter, Arial", color=BLANC),
                    margin=dict(l=16, r=16, t=52, b=16), height=300,
                    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR,
                                    font_size=12, font_color=BLANC),
                    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=10),
                                orientation="h", yanchor="bottom", y=1.02),
                )
                fig1.update_xaxes(
                    title=dict(text="Époque", font=dict(color=GRIS, size=10)),
                    showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                    tickfont=dict(color=GRIS),
                )
                fig1.update_yaxes(
                    title_text="Loss", title_font=dict(color=GRIS, size=10),
                    showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                    tickfont=dict(color=GRIS),
                )
                graphiques['apprentissage_cann'] = fig1

        except Exception as e:
            logger.warning(f"G1 CANN learning curves échoué : {e}")

        # ── G2 : COURBES D'APPRENTISSAGE TABNET ──────────────────────────────
        try:
            hist_tab = res_tabnet.get('historique', [])
            if hist_tab:
                epochs_t   = list(range(1, len(hist_tab) + 1))
                # ⚠️ Même défaut que G1 : `_calibrer_tabnet` empile
                # {'epoch','train','val'}. Voir le commentaire de G1.
                loss_tr_t  = [h.get('train', 0.0) for h in hist_tab]
                loss_va_t  = [h.get('val',   0.0) for h in hist_tab]

                fig2 = go.Figure()

                fig2.add_trace(go.Scatter(
                    x=epochs_t, y=loss_tr_t, mode='lines', name='Loss Train',
                    line=dict(color=BLEU, width=2, shape='spline', smoothing=0.4),
                    hovertemplate="Époque %{x}<br>Loss Train : <b>%{y:.4f}</b><extra></extra>",
                ))

                fig2.add_trace(go.Scatter(
                    x=epochs_t, y=loss_va_t, mode='lines', name='Loss Val',
                    line=dict(color=ROUGE, width=2, shape='spline', smoothing=0.4, dash='dash'),
                    hovertemplate="Époque %{x}<br>Loss Val : <b>%{y:.4f}</b><extra></extra>",
                ))

                best_t = loss_va_t.index(min(loss_va_t)) + 1
                fig2.add_vline(
                    x=best_t, line_dash="dot", line_color=VERT, line_width=1.5,
                    annotation_text=f"Époque retenue {best_t}",
                    annotation_font=dict(color=VERT, size=9),
                )

                fig2.update_layout(
                    title=dict(text="📈 TabNet — Courbes d'apprentissage",
                               font=dict(color=BLANC, size=13), x=0.01),
                    paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
                    font=dict(family="Inter, Arial", color=BLANC),
                    margin=dict(l=16, r=16, t=52, b=16), height=300,
                    hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR,
                                    font_size=12, font_color=BLANC),
                    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=10),
                                orientation="h", yanchor="bottom", y=1.02),
                )
                fig2.update_xaxes(
                    title=dict(text="Époque", font=dict(color=GRIS, size=10)),
                    showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                    tickfont=dict(color=GRIS),
                )
                fig2.update_yaxes(
                    title_text="Loss", title_font=dict(color=GRIS, size=10),
                    showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                    tickfont=dict(color=GRIS),
                )
                graphiques['apprentissage_tabnet'] = fig2

        except Exception as e:
            logger.warning(f"G2 TabNet learning curves échoué : {e}")

        # ── G3 : COMPARAISON GINI DL vs ML vs GLM ────────────────────────────
        try:
            noms_comp, ginis_comp, colors_comp, familles = [], [], [], []

            # DL (A5)
            for nom, met in self.metriques.items():
                noms_comp.append(nom.upper())
                ginis_comp.append(met.get('gini_test', 0))
                colors_comp.append(BLEU)
                familles.append('Deep Learning')

            # ML (A4)
            if result_a4 and result_a4.get('success'):
                for c in result_a4.get('classement', [])[:4]:
                    if 'GLM' not in c.get('famille', '').upper():
                        noms_comp.append(c['modele'].upper())
                        ginis_comp.append(c.get('gini_test', 0))
                        colors_comp.append(OR)
                        familles.append('ML')

            # GLM (A3)
            if result_a3 and result_a3.get('success'):
                for nom_g, met_g in result_a3.get('metriques', {}).items():
                    gini_g = met_g.get('gini', 0) if isinstance(met_g, dict) else 0
                    noms_comp.append(f"GLM {nom_g.upper()}")
                    ginis_comp.append(gini_g)
                    colors_comp.append(GRIS)
                    familles.append('GLM')

            if noms_comp:
                # Tri par Gini décroissant
                ordre = sorted(range(len(ginis_comp)), key=lambda i: ginis_comp[i], reverse=True)
                noms_s   = [noms_comp[i]   for i in ordre]
                ginis_s  = [ginis_comp[i]  for i in ordre]
                colors_s = [colors_comp[i] for i in ordre]
                fams_s   = [familles[i]    for i in ordre]

                fig3 = go.Figure()
                fig3.add_trace(go.Bar(
                    x             = noms_s,
                    y             = ginis_s,
                    marker_color  = colors_s,
                    marker_line   = dict(color=NAVY, width=1),
                    width         = 0.5,
                    opacity       = 0.88,
                    text          = [f"{g:.3f}" for g in ginis_s],
                    textposition  = 'outside',
                    textfont      = dict(color=BLANC, size=10),
                    hovertemplate = (
                        "<b>%{x}</b><br>"
                        "Gini : <b>%{y:.4f}</b><br>"
                        "<extra></extra>"
                    ),
                ))

                # Annotations familles
                for i, (n, f) in enumerate(zip(noms_s, fams_s)):
                    fig3.add_annotation(
                        x=i, y=-0.02, xref='x', yref='paper',
                        text=f"<span style='font-size:8px;color:{GRIS}'>{f}</span>",
                        showarrow=False, yanchor='top',
                    )

                layout3 = dict(**LAYOUT_BASE)
                layout3.update(dict(
                    title=dict(
                        text="🏆 Comparaison Gini — DL · ML · GLM",
                        font=dict(color=BLANC, size=13), x=0.01,
                    ),
                    xaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                    yaxis=dict(visible=False),
                    bargap=0.3,
                    annotations=layout3.get('annotations', []) + [dict(
                        x=0.98, y=0.97, xref='paper', yref='paper',
                        text="🔵 Deep Learning · 🟡 ML · ⬜ GLM",
                        showarrow=False, font=dict(color=GRIS, size=9),
                        xanchor='right',
                    )],
                ))
                fig3.update_layout(**layout3)
                graphiques['comparaison_gini'] = fig3

        except Exception as e:
            logger.warning(f"G3 comparaison Gini échoué : {e}")

        # ── G4 : FEATURE IMPORTANCE TABNET ───────────────────────────────────
        try:
            if importance_tabnet:
                noms_fi = list(importance_tabnet.keys())
                vals_fi = list(importance_tabnet.values())

                # Tri décroissant
                ordre_fi = sorted(range(len(vals_fi)), key=lambda i: vals_fi[i], reverse=True)
                noms_fi  = [noms_fi[i] for i in ordre_fi]
                vals_fi  = [vals_fi[i] for i in ordre_fi]

                # Couleur dégradée or → gris
                n_fi    = len(noms_fi)
                colors_fi = [
                    f"rgba(201,168,76,{max(0.3, 1 - i/n_fi*0.7):.2f})"
                    for i in range(n_fi)
                ]

                fig4 = go.Figure(go.Bar(
                    x             = vals_fi,
                    y             = noms_fi,
                    orientation   = 'h',
                    marker_color  = colors_fi,
                    marker_line   = dict(color=NAVY, width=1),
                    width         = 0.6,
                    opacity       = 0.9,
                    text          = [f"{v:.3f}" for v in vals_fi],
                    textposition  = 'outside',
                    textfont      = dict(color=BLANC, size=10),
                    hovertemplate = (
                        "<b>%{y}</b><br>"
                        "Importance attention : <b>%{x:.4f}</b><extra></extra>"
                    ),
                ))

                layout4 = dict(**LAYOUT_BASE)
                layout4.update(dict(
                    title=dict(
                        text="🔍 Feature Importance TabNet — Poids d'attention",
                        font=dict(color=BLANC, size=13), x=0.01,
                    ),
                    xaxis=dict(
                        title=dict(text="Importance (attention weight)",
                                   font=dict(color=GRIS, size=10)),
                        showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                        tickfont=dict(color=GRIS), zeroline=False,
                    ),
                    yaxis=dict(tickfont=dict(color=BLANC, size=9), showgrid=False),
                    height=max(280, n_fi * 30 + 80),
                ))
                fig4.update_layout(**layout4)
                graphiques['importance_tabnet'] = fig4

        except Exception as e:
            logger.warning(f"G4 importance TabNet échoué : {e}")

        return graphiques


    def _valider_hypotheses_dl(
        self,
        classement:   list,
        metriques:    dict,
        n_epochs:     int = 0,
        result_a3:    dict | None = None,
        historiques:  dict | None = None,
    ) -> dict:
        """
        Validation complète des hypothèses Deep Learning actuariel.

        H1 — Convergence de l'entraînement
             Loss décroissante sur les époques d'entraînement ✅
             Loss finale < Loss initiale / 2 → bonne convergence

        H2 — Absence de surapprentissage (Gini test / Gini train)
             ⚠️ La docstring annonçait un ratio de LOSS (val/train, seuils 1.3
             et 1.5) ; le code compare depuis toujours les GINI, avec des
             seuils de sens inverse (0.88 et 0.75). Le libellé publié disait
             lui aussi « Ratio val/train ». C'est le Gini qui est comparé.
             Ratio ≥ 0.88 → pas de surapprentissage ✅
             Ratio < 0.75 → surapprentissage significatif ❌

        H3 — Performance vs GLM de référence
             Gini DL > Gini GLM référence (0.12) → apport du DL ✅
             Gini DL ≈ Gini GLM → DL non justifié (complexité inutile)
        """
        import numpy as np

        # H1 — Convergence
        # ⚠️ H1 NE SIMULE PLUS SES LOSSES. Le code posait `loss_init = 0.50`
        # en dur et déduisait `loss_final` du Gini : la « convergence » ne
        # regardait donc PAS l'entraînement, et son verdict était une
        # fonction du seul Gini — deux calibrations aux historiques opposés
        # rendaient le même statut. L'historique réel est empilé époque par
        # époque par `_calibrer_cann` / `_calibrer_tabnet` ({'epoch','train',
        # 'val'}) ; c'est lui qui est lu ici, sur le modèle de tête.
        # ⚠️⚠️ ON CHERCHE LE MEILLEUR MODÈLE **DL**, PAS LE PREMIER DU
        # CLASSEMENT. Mesuré le 29/08/2026 sur deux runs réels : le classement
        # d'A5 contient aussi le GLM d'A3 et le meilleur ML d'A4.
        #
        #   portefeuille 2500 : tete = CANN               -> courbe 3 points
        #   portefeuille 3000 : tete = 'GLM Poisson (A3)' -> courbe 0 point
        #                       (cann=3 et tabnet=3 historiques EXISTAIENT)
        #
        # `historiques.get('glm poisson (a3)')` ne trouvait rien, et H1
        # publiait « convergence NON mesurée », statut ROUGE — **un verdict
        # sur la convergence du DL rendu faux par la victoire d'un GLM.**
        # *Le verdict portait sur le mauvais objet.*
        #
        # ⚠️ ON FILTRE PAR LA DONNÉE PRÉSENTE, PAS PAR UNE ÉTIQUETTE. Le
        # classement porte bien un champ `type == 'Deep Learning'`, mais s'y
        # fier ferait dépendre un verdict d'un libellé — le défaut que ce
        # chantier poursuit. Seuls les modèles DL ont un historique
        # d'entraînement : **avoir une entrée dans `historiques` EST le
        # critère**, et il ne peut pas mentir.
        # ⚠️ On parcourt dans l'ORDRE DU CLASSEMENT : le premier trouvé est
        # donc bien le MEILLEUR des DL, pas un DL au hasard.
        histo_h1 = []
        _modele_h1 = ''
        if classement and historiques:
            for _c in classement:
                _cle = str(_c.get('modele', '')).strip().lower()
                if historiques.get(_cle):
                    histo_h1, _modele_h1 = historiques[_cle], _c.get('modele', '')
                    break

        if classement and histo_h1:
            # ⚠️ LE NOM SUIT L'HISTORIQUE. H1 parle de la convergence du modèle
            # DONT ON LIT LES PERTES — nommer `classement[0]` ferait dire
            # « GLM Poisson (A3) a bien convergé » sur l'historique du CANN.
            # *Le libellé doit désigner l'objet mesuré, pas son voisin.*
            modele_nm  = _modele_h1 or classement[0].get('modele', 'DL')
            _pertes    = [float(h.get('train', 0.0)) for h in histo_h1]
            loss_init  = _pertes[0]
            loss_final = _pertes[-1]
            ratio_conv = loss_final / loss_init if loss_init else 1.0

            if ratio_conv < 0.5:
                h1_statut = "VERT"
                h1_msg    = f"Loss finale = {loss_final:.3f} ({ratio_conv*100:.0f}% de la loss initiale) → Convergence ✅"
                h1_conseil= f"{modele_nm} a bien convergé — entraînement réussi"
            elif ratio_conv < 0.7:
                h1_statut = "AMBRE"
                h1_msg    = f"Loss finale = {loss_final:.3f} ({ratio_conv*100:.0f}% de la loss initiale) → Convergence partielle ⚠️"
                h1_conseil= "Augmenter le nombre d'époques ou ajuster le learning rate"
            else:
                h1_statut = "ROUGE"
                h1_msg    = f"Loss finale = {loss_final:.3f} ({ratio_conv*100:.0f}% de la loss initiale) → Pas de convergence ❌"
                h1_conseil= "Vérifier l'architecture · Normaliser les features · Réduire le learning rate"
        else:
            # ⚠️ `modele_nm` EST RELU DU CLASSEMENT, PAS ÉCRASÉ EN "DL" : il
            # nomme le modèle retenu jusque dans le verdict global et dans la
            # synthèse publiée (l. 1986, 2021). Un repli qui l'écrase ferait
            # publier « DL » à la place du modèle réellement calibré.
            # Une hypothèse non mesurée se dit non mesurée : elle ne devient
            # pas VERTE, et le message le nomme.
            modele_nm  = classement[0].get('modele', 'DL') if classement else "DL"
            ratio_conv, loss_init, loss_final = 1.0, 0.0, 0.0
            h1_statut  = "ROUGE"
            if classement:
                h1_msg     = ("Historique d'entraînement indisponible → "
                              "convergence NON mesurée ❌")
                h1_conseil = (f"Le verdict de convergence de {modele_nm} ne peut "
                              f"pas être rendu : relancer la calibration pour "
                              f"disposer des pertes par époque")
            else:
                h1_msg    = "Aucun modèle DL calibré"
                h1_conseil= "Vérifier les données d'entrée et les dépendances PyTorch"

        # H2 — Surapprentissage (Gini test / Gini train du modèle de tête)
        # ⚠️ LE GINI D'APPRENTISSAGE N'EST PLUS FABRIQUÉ. Le code posait
        # `gini_train = gini_test * 1.15`, si bien que le ratio valait
        # 1/1,15 = 0,870 QUELLES QUE SOIENT LES DONNÉES : une constante, juste
        # sous le seuil VERT de 0,88 — H2 sortait AMBRE sur tout portefeuille,
        # y compris un modèle sans le moindre surapprentissage. Le vrai Gini
        # d'apprentissage est calculé et stocké par `_calibrer_*`
        # (clé `gini_train`) : c'est lui qui est lu.
        gini_cann   = metriques.get('cann',   {}).get('gini_test', 0)
        gini_tabnet = metriques.get('tabnet', {}).get('gini_test', 0)
        _tete_h2    = 'cann' if gini_cann >= gini_tabnet else 'tabnet'
        gini_test_h2 = metriques.get(_tete_h2, {}).get('gini_test', 0)
        gini_train  = metriques.get(_tete_h2, {}).get('gini_train', 0)
        ratio_of    = gini_test_h2 / max(gini_train, 0.001)

        if ratio_of >= 0.88:
            h2_statut = "VERT"
            h2_msg    = f"Gini test/train = {ratio_of:.3f} ≥ 0.88 → Pas de surapprentissage ✅"
            h2_conseil= "Le modèle DL généralise correctement sur données non vues"
        elif ratio_of >= 0.75:
            h2_statut = "AMBRE"
            h2_msg    = f"Gini test/train = {ratio_of:.3f} ∈ [0.75, 0.88] → Surapprentissage léger ⚠️"
            h2_conseil= "Augmenter le dropout · Réduire la taille du réseau · Ajouter régularisation L2"
        else:
            h2_statut = "ROUGE"
            h2_msg    = f"Gini test/train = {ratio_of:.3f} < 0.75 → Surapprentissage ❌"
            h2_conseil= "Modèle trop complexe pour les données — simplifier l'architecture"

        # H3 — Apport du DL vs GLM de référence
        # Gini de référence GLM — dynamique depuis A3 ou défaut 0.10
        gini_glm_ref = 0.10  # défaut neutre si A3 non fourni
        if result_a3 and result_a3.get('success'):
            gini_glm_ref = (
                result_a3.get('metriques', {})
                .get('poisson', {})
                .get('gini', 0.10)
            )
        # ⚠️⚠️ LE PLANCHER À ZÉRO PUBLIAIT UN CHIFFRE QU'AUCUN MODÈLE N'AVAIT
        # ATTEINT — part vivante du constat `a5/C1`. `max(..., 0)` écrasait un
        # Gini NÉGATIF vers 0, et le message publié disait « Gini DL = 0.0000 »
        # là où la mesure valait **−0,1103** (mesuré sur un portefeuille où le
        # DL ne discrimine pas). Le VERDICT restait ROUGE — il l'est dans les
        # deux cas — mais **le nombre montré à l'actuaire était faux**.
        #
        # ⚠️ C'est la même famille que `a3/C6` (« le Gini du Tweedie vaut 0
        # partout ») : *un zéro qui signifie « écrêté » est indiscernable d'un
        # zéro mesuré*. On publie donc la valeur RÉELLE, y compris négative —
        # un Gini négatif est une information, pas une erreur d'affichage :
        # il dit que le modèle classe À L'ENVERS.
        gini_dl_max  = max(gini_cann, gini_tabnet)
        gain_dl      = gini_dl_max - gini_glm_ref

        if gain_dl >= 0.05:
            h3_statut = "VERT"
            h3_msg    = f"Gini DL = {gini_dl_max:.4f} vs GLM = {gini_glm_ref:.4f} → Gain = +{gain_dl:.4f} ✅"
            h3_conseil= "Le Deep Learning apporte un gain significatif vs GLM — utilisation justifiée"
        elif gain_dl >= 0.02:
            h3_statut = "VERT"
            h3_msg    = f"Gini DL = {gini_dl_max:.4f} vs GLM = {gini_glm_ref:.4f} → Gain = +{gain_dl:.4f} ✅"
            h3_conseil= "Gain modéré — peser complexité vs performance pour la production"
        elif gain_dl >= 0:
            h3_statut = "AMBRE"
            h3_msg    = f"Gini DL = {gini_dl_max:.4f} vs GLM = {gini_glm_ref:.4f} → Gain = +{gain_dl:.4f} ⚠️"
            h3_conseil= "DL marginalement meilleur — privilégier GLM pour l'interprétabilité ACPR"
        else:
            h3_statut = "ROUGE"
            h3_msg    = f"Gini DL = {gini_dl_max:.4f} < GLM = {gini_glm_ref:.4f} → DL moins performant ❌"
            h3_conseil= "Utiliser le GLM — DL non justifié sur ces données"

        statuts = [h1_statut, h2_statut, h3_statut]
        statut_global = "ROUGE" if "ROUGE" in statuts else "AMBRE" if "AMBRE" in statuts else "VERT"
        conclusion = {
            "VERT":  f"✅ Deep Learning validé — {modele_nm} prêt pour la production actuarielle",
            "AMBRE": "⚠️ Deep Learning utilisable avec précautions — vérifier les points signalés",
            "ROUGE": "❌ Deep Learning non recommandé — utiliser GLM ou ML classique",
        }[statut_global]

        return {
            "h1_convergence": {
                "loss_init":   round(loss_init, 4),
                "loss_final":  round(loss_final, 4),
                "ratio_conv":  round(ratio_conv, 4),
                # ⚠️⚠️ LA COURBE RÉELLE, PORTÉE JUSQU'À LA FIGURE — constat
                # `a5/C4`. H1 avait cessé de simuler ses losses ; la FIGURE,
                # elle, continuait de tracer une exponentielle analytique
                # bruitée sur 50 époques codées en dur. *Le correctif était
                # arrivé à côté de la surface qu'il devait couvrir.*
                # ⚠️ Elle passe par `h1_convergence` plutôt que par un
                # nouveau paramètre : la figure lit DÉJÀ ce dictionnaire, et
                # loss_init/loss_final en viennent. Une seconde voie
                # d'alimentation aurait pu diverger de la première.
                # ⚠️ VIDE quand l'historique manque — la figure le DÉCLARE
                # alors, elle ne fabrique plus rien.
                "courbe": [
                    {"epoch": int(h.get("epoch", i + 1)),
                     "train": float(h.get("train", 0.0)),
                     "val":   float(h.get("val", 0.0))}
                    for i, h in enumerate(histo_h1)
                ],
                "statut":      h1_statut,
                "message":     h1_msg,
                "conseil":     h1_conseil,
                "titre_graphique": f"{'✅' if h1_statut=='VERT' else '⚠️' if h1_statut=='AMBRE' else '❌'} Convergence — Loss finale {loss_final:.3f} ({ratio_conv*100:.0f}% initiale)",
            },
            "h2_surapprentissage": {
                "ratio_of":    round(ratio_of, 4),
                "gini_train":  round(gini_train, 4),
                "gini_val":    round(max(gini_cann, gini_tabnet), 4),
                "statut":      h2_statut,
                "message":     h2_msg,
                "conseil":     h2_conseil,
                "titre_graphique": f"{'✅' if h2_statut=='VERT' else '⚠️' if h2_statut=='AMBRE' else '❌'} Surapprentissage — Gini test/train = {ratio_of:.3f}",
            },
            "h3_apport_dl": {
                "gini_dl":     round(gini_dl_max, 4),
                "gini_glm":    round(gini_glm_ref, 4),
                "gain":        round(gain_dl, 4),
                "statut":      h3_statut,
                "message":     h3_msg,
                "conseil":     h3_conseil,
                "titre_graphique": f"{'✅' if h3_statut=='VERT' else '⚠️' if h3_statut=='AMBRE' else '❌'} Apport DL vs GLM — Gain Gini = {gain_dl:+.4f}",
            },
            "statut_global": statut_global,
            "conclusion":    conclusion,
            "modele_retenu": modele_nm,
        }

    def _graphiques_validation_dl(
        self,
        val_dl:     Dict,
        classement: list,
        metriques:  Dict,
    ) -> Dict:
        """4 graphiques auto-explicatifs validation Deep Learning."""
        # ⚠️ `numpy` A DISPARU DE CET IMPORT, ET C'EST UN SIGNAL. Il ne servait
        # qu'à FABRIQUER la courbe de convergence (`np.exp`, `np.random`).
        # Depuis `a5/C4`, ces figures ne calculent plus rien : elles tracent ce
        # qu'on leur donne. *Une dépendance qui disparaît parce qu'on a cessé
        # d'inventer est une bonne nouvelle, pas un nettoyage.*
        try:
            import plotly.graph_objects as go
        except ImportError:
            return {}

        NAVY="#0F2E52"; NAVY_L="#1B3A5C"; NAVY_LL="#243F6A"
        OR="#C9A84C"; BLANC="#F0F4F8"; GRIS="#8A9AB0"
        VERT = couleur_rag("VERT", FOND_SOMBRE)
        ROUGE = couleur_rag("ROUGE", FOND_SOMBRE)
        AMBRE = couleur_rag("AMBRE", FOND_SOMBRE); BLEU="#3498DB"
        LAYOUT = dict(
            paper_bgcolor=NAVY, plot_bgcolor=NAVY_L,
            font=dict(family="Inter, Arial", color=BLANC, size=11),
            margin=dict(l=16, r=16, t=60, b=50), height=300,
            hoverlabel=dict(bgcolor=NAVY_LL, bordercolor=OR, font_size=12, font_color=BLANC),
        )
        graphiques = {}

        # ══════════════════════════════════════════════════════════════════════
        # G1 — COURBE DE CONVERGENCE : LES VRAIES PERTES, PLUS AUCUNE SIMULATION
        # ══════════════════════════════════════════════════════════════════════
        # ⚠️⚠️ CONSTAT `a5/C4`. Cette figure traçait une EXPONENTIELLE
        # ANALYTIQUE — `loss_init * exp(-3e/50) + loss_final * (1 - exp(-3e/50))`
        # — bruitée par un `np.random.normal()` NON SEMÉ, sur **50 époques
        # codées en dur**. Mesuré : le run réel en faisait **3**. La légende
        # promettait pourtant « La loss doit diminuer régulièrement ».
        #
        # ⚠️⚠️ ET LE REMÈDE N'EST PAS DE SEMER LE BRUIT. Semer rendrait une
        # courbe FABRIQUÉE reproductible, donc crédible — on aurait échangé un
        # défaut visible contre un défaut invisible. Les vraies pertes existent
        # déjà : `_calibrer_cann` / `_calibrer_tabnet` empilent
        # `{'epoch','train','val'}` époque par époque, et `h1_convergence` les
        # porte désormais sous `courbe`.
        #
        # ⚠️ QUAND L'HISTORIQUE MANQUE, ON LE DIT. La figure ne se rabat sur
        # aucune formule : elle déclare l'absence, comme les sept figures de
        # `core/charts_tarif` depuis `charts/C3`.
        try:
            h1 = val_dl["h1_convergence"]
            _courbe = h1.get("courbe") or []
            epochs     = [int(p["epoch"]) for p in _courbe]
            train_loss = [float(p["train"]) for p in _courbe]
            val_loss   = [float(p["val"]) for p in _courbe]
            n_ep       = len(epochs)

            statut_h1  = h1["statut"]
            # ⚠️ `couleur_h1` RETIRÉE : tous ses usages étaient du TEXTE, et ils
            # lisent désormais `couleur_h1_txt`. *Une couleur d'objet qui ne sert
            # jamais d'objet n'a pas lieu d'être.*
            # ⚠️ AUCUN TEXTE EN ROUGE — arbitré. La couleur ci-dessus reste
            # pour les OBJETS (barre, ligne, jauge) ; celle-ci sert au TEXTE.
            couleur_h1_txt = couleur_texte_rag(statut_h1)

            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(
                x=epochs, y=train_loss, mode="lines", name="Loss Train",
                line=dict(color=OR, width=2.5),
                hovertemplate="Époque %{x}<br>Loss Train : %{y:.4f}<extra></extra>",
            ))
            fig1.add_trace(go.Scatter(
                x=epochs, y=val_loss, mode="lines", name="Loss Validation",
                line=dict(color=BLEU, width=2, dash="dash"),
                hovertemplate="Époque %{x}<br>Loss Val : %{y:.4f}<extra></extra>",
            ))
            # Zone de convergence — sur le DERNIER TIERS RÉEL, plus sur 50.
            # ⚠️ Elle n'a de sens qu'avec assez d'époques pour qu'un « dernier
            # tiers » existe : sur 3 époques, elle désignerait presque toute la
            # courbe. Un repère qui couvre tout ne repère rien.
            if n_ep >= 6:
                fig1.add_vrect(x0=epochs[int(n_ep * 0.7)], x1=epochs[-1],
                               fillcolor="rgba(46,204,113,0.06)", line_width=0,
                               annotation_text="Convergence",
                               annotation_font=dict(color=VERT, size=9))
            l1 = dict(**LAYOUT)
            l1.update(dict(
                title=dict(
                    text=h1["titre_graphique"],
                    font=dict(color=couleur_h1_txt, size=11), x=0.01
                ),
                xaxis=dict(title="Époques", tickfont=dict(color=GRIS), showgrid=True,
                          gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(title="Loss", tickfont=dict(color=GRIS), showgrid=True,
                          gridcolor="rgba(255,255,255,0.05)"),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=BLANC, size=9),
                           orientation="h", yanchor="bottom", y=1.0),
                # ⚠️ LA FIGURE DIT SUR COMBIEN D'ÉPOQUES ELLE PORTE. Le
                # nombre venait d'un `50` codé en dur qui ne correspondait à
                # aucun run ; il est désormais celui de l'historique tracé.
                annotations=[dict(
                    text=(f"💡 La loss doit diminuer régulièrement (courbe "
                          f"descend). Si elle remonte = surapprentissage. — "
                          f"{n_ep} époque(s) réellement effectuée(s)."),
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig1.update_layout(**l1)
            # ⚠️⚠️ L'ABSENCE SE DÉCLARE AU CENTRE DE LA FIGURE — leçon de
            # `charts/C3`. Un graphique vide est indiscernable d'un graphique
            # plein pour qui feuillette le rapport.
            # ⚠️ APRÈS `update_layout` À DESSEIN : `l1` porte sa propre liste
            # `annotations`, qui REMPLACE. Je l'ai posée avant en écrivant ce
            # lot, et le test l'a attrapée — *une annotation silencieusement
            # écrasée est exactement le défaut qu'on corrige ici.*
            if not _courbe:
                fig1.add_annotation(
                    text=("AUCUNE DONNÉE — historique d'entraînement<br>"
                          "<i>la convergence n'est pas mesurée</i>"),
                    xref="paper", yref="paper", x=0.5, y=0.5,
                    showarrow=False, align="center",
                    # ⚠️ Littéral et non `dict(...)` : le fichier compte 112
                    # `dict()` que ruff signale (C408), tous antérieurs. En
                    # ajouter un 113e ferait échouer la propreté du lot. On ne
                    # convertit pas les 112 ici — ce n'est pas ce chantier.
                    font={'color': BLANC, 'size': 13})
            graphiques["convergence_loss"] = fig1
        except Exception as e:
            logger.warning(f"G1 convergence : {e}")

        # ══════════════════════════════════════════════════════════════════════
        # G2 — DL vs GLM : UN MODÈLE NON CALIBRÉ N'EST PAS UN MODÈLE À ZÉRO
        # ══════════════════════════════════════════════════════════════════════
        # ⚠️⚠️ CONSTAT `a5/C5`, ET SA PREMIÈRE CAUSE ÉTAIT DÉJÀ CORRIGÉE. Le
        # relevé mesurait `barres [GLM, CANN, TabNet] = [0.14, 0, 0]` pour des
        # Gini réels `[0.4781, 0.0950]` : la figure lisait alors la mauvaise
        # clé. Elle lit la bonne aujourd'hui.
        #
        # ⚠️⚠️ MAIS LE SYMPTÔME SE REPRODUISAIT ENCORE, PAR UNE AUTRE CAUSE —
        # mesuré le 29/08/2026 :
        #
        #   les deux modeles ENTRAINES        barres = [0.14, 0.4781, 0.095]
        #   CANN ABSENT (calibration echouee) barres = [0.14, 0.0,    0.095]
        #   LES DEUX ABSENTS                  barres = [0.14, 0.0,    0.0]
        #
        # `self.metriques['cann']` n'existe QUE si la calibration a réussi ;
        # le `.get(..., 0)` transformait une absence en performance nulle.
        # **La dernière ligne reproduit exactement les nombres du relevé.**
        # *Un zéro qui signifie « jamais entraîné » est indiscernable d'un zéro
        # mesuré* — c'est la leçon d'`a3/C6` (le Gini du Tweedie) et du
        # plancher d'A5.
        #
        # ⚠️ ON N'INVENTE PAS DE VALEUR : le modèle absent est RETIRÉ de la
        # figure, et son absence est ÉCRITE sous l'axe — patron de `charts/C5`
        # (« n tracées sur m fournies »). La légende, elle, promet que les
        # barres DL « doivent dépasser la ligne GLM » : une barre fantôme à
        # zéro la faisait mentir.
        try:
            h3 = val_dl["h3_apport_dl"]
            _dl_possibles = (("CANN (Wüthrich)", "cann"), ("TabNet", "tabnet"))
            _absents = [lib for lib, cle in _dl_possibles
                        if "gini_test" not in (metriques.get(cle) or {})]
            modeles_comp = ["GLM Poisson (ref)"] + [
                lib for lib, cle in _dl_possibles
                if "gini_test" in (metriques.get(cle) or {})]
            ginis_comp   = [h3["gini_glm"]] + [
                metriques[cle]["gini_test"] for _, cle in _dl_possibles
                if "gini_test" in (metriques.get(cle) or {})]
            # ⚠️ La palette suit le nombre de barres RÉELLEMENT tracées : une
            # liste de trois couleurs sur deux barres laisserait la troisième
            # sans usage, et une barre retirée décalerait les couleurs.
            colors_comp = [GRIS, BLEU, OR][:len(modeles_comp)]
            statut_h3   = h3["statut"]
            # ⚠️ `couleur_h3` RETIRÉE : tous ses usages étaient du TEXTE, et ils
            # lisent désormais `couleur_h3_txt`. *Une couleur d'objet qui ne sert
            # jamais d'objet n'a pas lieu d'être.*
            # ⚠️ AUCUN TEXTE EN ROUGE — arbitré. La couleur ci-dessus reste
            # pour les OBJETS (barre, ligne, jauge) ; celle-ci sert au TEXTE.
            couleur_h3_txt = couleur_texte_rag(statut_h3)

            fig2 = go.Figure(go.Bar(
                x=modeles_comp, y=ginis_comp,
                marker_color=colors_comp,
                marker_line=dict(color=NAVY, width=1),
                width=0.4, opacity=0.88,
                text=[f"{g:.4f}" for g in ginis_comp],
                textposition="outside",
                textfont=dict(color=BLANC, size=11),
                hovertemplate="<b>%{x}</b><br>Gini : %{y:.4f}<extra></extra>",
            ))
            fig2.add_hline(y=h3["gini_glm"], line_color=GRIS, line_width=1.5, line_dash="dot",
                          annotation_text=f"Référence GLM {h3['gini_glm']:.4f}",
                          annotation_font=dict(color=GRIS, size=9))
            l2 = dict(**LAYOUT)
            l2.update(dict(
                title=dict(
                    text=h3["titre_graphique"],
                    font=dict(color=couleur_h3_txt, size=11), x=0.01
                ),
                xaxis=dict(tickfont=dict(color=BLANC), showgrid=False),
                yaxis=dict(visible=False), bargap=0.35, showlegend=False,
                # ⚠️ CE QUI N'EST PAS TRACÉ EST ÉCRIT. Un modèle absent de la
                # figure sans un mot laisserait croire qu'il n'existe pas,
                # alors qu'il a été TENTÉ et a échoué — deux choses très
                # différentes pour qui valide le modèle.
                annotations=[dict(
                    text=("💡 Les barres bleue/dorée doivent dépasser la ligne "
                          "pointillée (GLM). Si non → DL non justifié."
                          + (f"<br>⚠ Non tracé(s), car non calibré(s) : "
                             f"{', '.join(_absents)} — absence, pas Gini nul."
                             if _absents else "")),
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig2.update_layout(**l2)
            # ⚠️⚠️ AUCUN MODÈLE DL TRACÉ : la figure le DÉCLARE au centre plutôt
            # que de montrer une barre GLM solitaire sous une légende qui parle
            # de « barres bleue/dorée » inexistantes. Leçon de `charts/C3`, et
            # posée APRÈS `update_layout`, qui remplace les annotations.
            if len(modeles_comp) == 1:
                fig2.add_annotation(
                    text=("AUCUNE DONNÉE — aucun modèle Deep Learning calibré"
                          "<br><i>l'apport du DL n'est pas mesurable ici</i>"),
                    xref="paper", yref="paper", x=0.5, y=0.5,
                    showarrow=False, align="center",
                    font={'color': BLANC, 'size': 13})
            graphiques["comparaison_dl_glm"] = fig2
        except Exception as e:
            logger.warning(f"G2 comparaison : {e}")

        # G3 — Jauge surapprentissage
        try:
            h2  = val_dl["h2_surapprentissage"]
            ratio = h2["ratio_of"]
            statut_h2  = h2["statut"]
            couleur_h2 = VERT if statut_h2=="VERT" else AMBRE if statut_h2=="AMBRE" else ROUGE
            # ⚠️ AUCUN TEXTE EN ROUGE — arbitré. La couleur ci-dessus reste
            # pour les OBJETS (barre, ligne, jauge) ; celle-ci sert au TEXTE.
            couleur_h2_txt = couleur_texte_rag(statut_h2)

            fig3 = go.Figure(go.Indicator(
                mode="gauge+number",
                value=ratio,
                title=dict(
                    text=h2["titre_graphique"],
                    font=dict(color=couleur_h2_txt, size=11)
                ),
                number=dict(font=dict(color=couleur_h2_txt, size=28), valueformat=".3f"),
                gauge=dict(
                    axis=dict(range=[0, 1.5], tickfont=dict(color=GRIS, size=8),
                             tickvals=[0, 0.75, 0.88, 1.0, 1.3, 1.5],
                             ticktext=["0", "0.75", "0.88", "1.0", "1.3", "1.5"]),
                    bar=dict(color=couleur_h2, thickness=0.25),
                    bgcolor=NAVY_L, borderwidth=0,
                    steps=[
                        dict(range=[0, 0.75],   color="rgba(231,76,60,0.12)"),
                        dict(range=[0.75, 0.88], color="rgba(243,156,18,0.12)"),
                        dict(range=[0.88, 1.5],  color="rgba(46,204,113,0.12)"),
                    ],
                    threshold=dict(line=dict(color=VERT, width=3), thickness=0.8, value=0.88),
                ),
            ))
            fig3.update_layout(
                paper_bgcolor=NAVY, font=dict(color=BLANC),
                margin=dict(l=30, r=30, t=80, b=50), height=300,
                annotations=[dict(
                    text=f"💡 {h2['conseil']}",
                    xref="paper", yref="paper", x=0.5, y=-0.12,
                    font=dict(color=GRIS, size=9), showarrow=False, align="center"
                )],
            )
            graphiques["jauge_surapprentissage"] = fig3
        except Exception as e:
            logger.warning(f"G3 surapprentissage : {e}")

        # G4 — Scorecard validation DL
        try:
            items = [
                ("H1 — Convergence entraînement", val_dl["h1_convergence"]["statut"],
                 val_dl["h1_convergence"]["message"], val_dl["h1_convergence"]["conseil"]),
                ("H2 — Absence surapprentissage", val_dl["h2_surapprentissage"]["statut"],
                 val_dl["h2_surapprentissage"]["message"], val_dl["h2_surapprentissage"]["conseil"]),
                ("H3 — Apport DL vs GLM", val_dl["h3_apport_dl"]["statut"],
                 val_dl["h3_apport_dl"]["message"], val_dl["h3_apport_dl"]["conseil"]),
            ]
            fig4 = go.Figure()
            for nom, statut, msg, conseil in items:
                couleur = VERT if statut=="VERT" else AMBRE if statut=="AMBRE" else ROUGE
                # ⚠️ AUCUN TEXTE EN ROUGE — arbitré. La couleur ci-dessus reste
                # pour les OBJETS (barre, ligne, jauge) ; celle-ci sert au TEXTE.
                couleur_txt = couleur_texte_rag(statut)
                # ⚠️ Le glyphe vient de la SOURCE UNIQUE — il était recopié à
                # l'identique dans les quatre agents. Correct partout ce jour-là,
                # et rien n'empêchait la cinquième copie de diverger.
                icone   = glyphe_rag(statut)
                score   = 1.0 if statut=="VERT" else 0.5 if statut=="AMBRE" else 0.0
                fig4.add_trace(go.Bar(
                    x=[score], y=[nom], orientation="h",
                    marker_color=couleur, width=0.5,
                    text=f"{icone} {statut}", textposition="outside",
                    textfont=dict(color=couleur_txt, size=10),
                    hovertemplate=f"<b>{nom}</b><br>{msg}<br>💡 {conseil}<extra></extra>",
                    showlegend=False,
                ))
            statut_g  = val_dl["statut_global"]
            # ⚠️ `couleur_g` RETIRÉE : tous ses usages étaient du TEXTE, et ils
            # lisent désormais `couleur_g_txt`. *Une couleur d'objet qui ne sert
            # jamais d'objet n'a pas lieu d'être.*
            # ⚠️ AUCUN TEXTE EN ROUGE — arbitré. La couleur ci-dessus reste
            # pour les OBJETS (barre, ligne, jauge) ; celle-ci sert au TEXTE.
            couleur_g_txt = couleur_texte_rag(statut_g)
            l4 = dict(**LAYOUT)
            l4.update(dict(
                title=dict(
                    text=f"Scorecard Deep Learning — {val_dl['conclusion']}",
                    font=dict(color=couleur_g_txt, size=10), x=0.01
                ),
                xaxis=dict(range=[0, 1.6], visible=False),
                yaxis=dict(tickfont=dict(color=BLANC, size=10), showgrid=False),
                barmode="overlay", height=260,
                annotations=[dict(
                    text="💡 3 ✅ = Deep Learning validé. Si H3 ❌ → utiliser GLM ou ML classique plus interprétable.",
                    xref="paper", yref="paper", x=0.01, y=-0.22,
                    font=dict(color=GRIS, size=9), showarrow=False, align="left"
                )],
            ))
            fig4.update_layout(**l4)
            graphiques["scorecard_validation_dl"] = fig4
        except Exception as e:
            logger.warning(f"G4 scorecard DL : {e}")

        return graphiques

    def _erreur(self, message: str, audit_id: str) -> Dict:
        return {
            'success':           False,
            'dataframe':         pd.DataFrame(),
            'branche':           None,
            'statut_rag':        'ROUGE',
            'modeles':           {},
            'metriques':         {},
            'classement':        [],
            'importance_tabnet': {},
            'rapport':           {},
            'commentaire':       f"❌ ERREUR A5 : {message}",
            'audit_id':          audit_id,
            'erreur':            message,
        }


if __name__ == '__main__':
    print("Agent A5 — Deep Learning ActuarIA v1.0")
    print("Modèles : CANN (Wüthrich 2019) + TabNet (Google 2021)")
    print("Usage   : %run 'chemin/a5_deep_learning.py'")
    print("          agent_a5 = AgentA5DeepLearning()")
    print("          result_a5 = agent_a5.run(result_a2, result_a3, result_a4)")
