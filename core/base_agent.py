# =============================================================================
#  ActuarIA — core/base_agent.py
#  Classe de base commune à tous les agents de la plateforme
#
#  Usage :
#    from core.base_agent import BaseAgent
#
#    class AgentA8StressTesting(BaseAgent):
#        AGENT_CODE    = 'A8'
#        AGENT_NOM     = 'Isabelle'
#        AGENT_VERSION = '1.0'
#
#        def run(self, ...):
#            ...
#            return self._succes(n1=n1, n2=n2, commentaire=commentaire)
#
#  ⚠️⚠️ CE MODULE N'A AUCUN HERITIER, ET C'EST MESURE (21/08/2026). Aucune
#  classe du depot n'ecrit `(BaseAgent)` : l'exemple ci-dessus est la SEULE
#  occurrence de ce nom hors de ce fichier. `AgentA7Provisionnement` et les
#  autres agents sont des classes autonomes.
#
#  ⚠️ CE QUE CELA REND THEORIQUE : `_sauvegarder_audit` existe ici en
#  `(audit_trail, audit_id)` et dans `a7_provisionnement/agent.py` en
#  `(audit_id, audit)` -- L'ORDRE EST INVERSE. Cette divergence a ete portee
#  a l'ardoise pendant plusieurs lots comme un risque. ELLE N'EN EST PAS UN
#  TANT QUE PERSONNE N'HERITE : les deux methodes ne se rencontrent jamais,
#  aucun `super()` ne les relie, et aucun appel polymorphe n'existe.
#
#  ⚠️ CE QUI RESTE VRAI : le jour ou une classe heritera d'ici, l'ordre
#  devra etre aligne AVANT. Ce commentaire est la pour que celui qui lira
#  << signature inversee >> sache ce qu'il en est, plutot que de corriger un
#  risque qui n'existe pas -- ou de croire qu'il n'en existera jamais.
#
# =============================================================================

import json
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger('actuaria')


# =============================================================================
#  DICT DE RETOUR STANDARDISÉ
#  Toutes les clés que tout agent DOIT retourner
# =============================================================================

RETOUR_VIDE = {
    # ── Statut ────────────────────────────────────────────────────────────────
    'success':      False,
    'statut_rag':   'ROUGE',         # VERT / AMBRE / ROUGE
    'erreur':       None,
    # ── Résultats structurés ──────────────────────────────────────────────────
    'n1':           {},              # ingestion / validation données
    'n2':           {},              # hypothèses / validation méthodologique
    'n3':           {},              # calculs actuariels
    'n4':           {},              # best estimate / résultats finaux
    # ── Livrables ─────────────────────────────────────────────────────────────
    'graphiques':   {},              # dict {nom: go.Figure}
    'commentaire':  '',              # narration textuelle
    'excel_bytes':  b'',            # fichier Excel
    'word_bytes':   b'',            # rapport Word
    'pdf_bytes':    b'',            # rapport PDF
    # ── Traçabilité ───────────────────────────────────────────────────────────
    'audit_trail':  {},
    'audit_id':     '',
    'triangle':     None,           # données brutes pour regénération graphiques
}


# =============================================================================
#  CLASSE DE BASE
# =============================================================================

class BaseAgent:
    """
    Classe de base commune à tous les agents ActuarIA.

    Attributes
    ----------
    AGENT_CODE    : str   — code agent (ex. 'A7', 'S1', 'EP1')
    AGENT_NOM     : str   — prénom agent (ex. 'Ibrahim', 'Léonie')
    AGENT_VERSION : str   — version (ex. '5.0')
    AGENT_DIR     : str   — direction (non_vie / sante_prev / vie_epre / data)

    Usage
    -----
    Hériter de BaseAgent, définir les attributs de classe, implémenter run().
    Utiliser self._succes() et self._echec() pour construire le dict retourné.
    """

    AGENT_CODE    : str = 'XX'
    AGENT_NOM     : str = 'Agent'
    AGENT_VERSION : str = '1.0'
    AGENT_DIR     : str = 'transversal'

    def __init__(
        self,
        models_path : str  = '/tmp/actuaria',
        audit_path  : str  = '/tmp/actuaria',
        verbose     : bool = False,
    ):
        self.models_path = Path(models_path)
        self.audit_path  = Path(audit_path)
        self.verbose     = verbose

        # Créer les répertoires si nécessaire
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.audit_path.mkdir(parents=True, exist_ok=True)

        # Logger spécifique à l'agent
        self.logger = logging.getLogger(
            f'actuaria.{self.AGENT_DIR}.{self.AGENT_CODE.lower()}'
        )

        if self.verbose:
            self.logger.info(
                f"[{self.AGENT_CODE}] {self.AGENT_NOM} v{self.AGENT_VERSION} initialisé"
            )

    # =========================================================================
    #  MÉTHODES UTILITAIRES INTERNES
    # =========================================================================

    def _log(self, msg: str, level: str = 'info') -> None:
        """Log conditionnel au niveau verbose."""
        if self.verbose:
            getattr(self.logger, level, self.logger.info)(
                f"[{self.AGENT_CODE}] {msg}"
            )

    def _generer_audit_id(self, suffixe: str = '') -> str:
        """Génère un identifiant d'audit unique."""
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        base = f"{self.AGENT_CODE}_{ts}"
        if suffixe:
            base += f"_{suffixe}"
        return base

    def _generer_hash(self, data: Any) -> str:
        """Génère un hash SHA-256 des données pour la traçabilité."""
        try:
            serialized = json.dumps(data, default=str, sort_keys=True)
            return hashlib.sha256(serialized.encode()).hexdigest()[:8].upper()
        except Exception:
            return 'HASH_ERR'

    def _init_audit(self, **kwargs) -> Dict:
        """
        Initialise le dict audit_trail avec les métadonnées de l'appel.
        kwargs : paramètres passés à run() pour traçabilité.
        """
        return {
            'agent_code':    self.AGENT_CODE,
            'agent_nom':     self.AGENT_NOM,
            'agent_version': self.AGENT_VERSION,
            'direction':     self.AGENT_DIR,
            'timestamp':     datetime.now().isoformat(),
            'parametres':    {
                k: str(v)[:200]  # tronquer les valeurs longues
                for k, v in kwargs.items()
                if v is not None and k not in ('source', 'dataframe', 'triangle')
            },
        }

    # =========================================================================
    #  CONSTRUCTEURS DE RETOUR STANDARDISÉ
    # =========================================================================

    def _succes(
        self,
        statut_rag  : str  = 'VERT',
        n1          : Dict = None,
        n2          : Dict = None,
        n3          : Dict = None,
        n4          : Dict = None,
        graphiques  : Dict = None,
        commentaire : str  = '',
        excel_bytes : bytes = b'',
        word_bytes  : bytes = b'',
        pdf_bytes   : bytes = b'',
        audit_trail : Dict = None,
        audit_id    : str  = '',
        triangle    : Any  = None,
        **extra,
    ) -> Dict:
        """
        Construit le dict de retour pour un succès.
        Garantit que toutes les clés standardisées sont présentes.
        """
        result = dict(RETOUR_VIDE)  # copie du template
        result.update({
            'success':      True,
            'statut_rag':   statut_rag,
            'erreur':       None,
            'n1':           n1          or {},
            'n2':           n2          or {},
            'n3':           n3          or {},
            'n4':           n4          or {},
            'graphiques':   graphiques  or {},
            'commentaire':  commentaire or '',
            'excel_bytes':  excel_bytes or b'',
            'word_bytes':   word_bytes  or b'',
            'pdf_bytes':    pdf_bytes   or b'',
            'audit_trail':  audit_trail or {},
            'audit_id':     audit_id    or self._generer_audit_id(),
            'triangle':     triangle,
        })
        # Clés supplémentaires spécifiques à l'agent
        result.update(extra)
        return result

    def _echec(
        self,
        erreur      : str  = 'Erreur inconnue',
        audit_trail : Dict = None,
        audit_id    : str  = '',
        **extra,
    ) -> Dict:
        """
        Construit le dict de retour pour un échec.
        Garantit que toutes les clés standardisées sont présentes.
        """
        self.logger.error(f"[{self.AGENT_CODE}] ÉCHEC : {erreur}")
        result = dict(RETOUR_VIDE)
        result.update({
            'success':      False,
            'statut_rag':   'ROUGE',
            'erreur':       str(erreur),
            'audit_trail':  audit_trail or {'erreur': str(erreur)},
            'audit_id':     audit_id    or self._generer_audit_id('ECHEC'),
        })
        result.update(extra)
        return result

    # =========================================================================
    #  MÉTHODE run() — À IMPLÉMENTER DANS CHAQUE AGENT
    # =========================================================================

    def run(self, **kwargs) -> Dict:
        """
        Point d'entrée principal de l'agent. À surcharger obligatoirement.

        Returns
        -------
        Dict avec toutes les clés standardisées (voir RETOUR_VIDE).
        Utiliser self._succes() ou self._echec() pour construire le retour.
        """
        raise NotImplementedError(
            f"L'agent {self.AGENT_CODE} ({self.AGENT_NOM}) "
            f"doit implémenter la méthode run()."
        )

    # =========================================================================
    #  MÉTHODES UTILITAIRES COMMUNES
    # =========================================================================

    def _valider_dataframe(self, df, colonnes_requises: List[str]) -> tuple:
        """
        Valide qu'un DataFrame contient les colonnes requises.

        Returns
        -------
        (ok: bool, message: str)
        """
        try:
            import pandas as pd
            if df is None:
                return False, "DataFrame None"
            if not isinstance(df, pd.DataFrame):
                return False, f"Type attendu DataFrame, reçu {type(df).__name__}"
            manquantes = [c for c in colonnes_requises if c not in df.columns]
            if manquantes:
                return False, f"Colonnes manquantes : {manquantes}"
            if df.empty:
                return False, "DataFrame vide"
            return True, f"{len(df):,} lignes · {len(df.columns)} colonnes"
        except Exception as e:
            return False, str(e)

    def _statut_rag(self, valeur: float, seuil_vert: float, seuil_ambre: float,
                    inverse: bool = False) -> str:
        """
        Calcule le statut RAG (VERT/AMBRE/ROUGE) pour un indicateur.

        Parameters
        ----------
        valeur      : valeur de l'indicateur
        seuil_vert  : seuil en dessous duquel c'est VERT (ou au-dessus si inverse)
        seuil_ambre : seuil en dessous duquel c'est AMBRE (ou au-dessus si inverse)
        inverse     : True si un score élevé est bon (ex. ratio SCR)
        """
        if inverse:
            if valeur >= seuil_vert:   return 'VERT'
            if valeur >= seuil_ambre:  return 'AMBRE'
            return 'ROUGE'
        else:
            if valeur <= seuil_vert:   return 'VERT'
            if valeur <= seuil_ambre:  return 'AMBRE'
            return 'ROUGE'

    def _sauvegarder_audit(self, audit_trail: Dict, audit_id: str) -> Optional[Path]:
        """
        Sauvegarde l'audit trail en JSON dans audit_path.

        Returns
        -------
        Path du fichier créé, ou None si échec.
        """
        try:
            chemin = self.audit_path / f"audit_{audit_id}.json"
            with open(chemin, 'w', encoding='utf-8') as f:
                json.dump(audit_trail, f, indent=2, ensure_ascii=False, default=str)
            return chemin
        except Exception as e:
            self.logger.warning(f"Audit non sauvegardé : {e}")
            return None
