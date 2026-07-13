# ActuarIA — core
# Modules transversaux communs à tous les agents
from .base_agent        import BaseAgent
from .audit_trail       import AuditTrail, AgentRafael
from .conformite_reglementaire import (
    filtrer_genre,
    filtrer_famille_cible,
    COLS_GENRE_INTERDITES,
    COLS_GENRE_STEMS,
    COLS_FAMILLE_CIBLE,
    COLS_FAMILLE_CIBLE_STEMS,
    COLS_FAMILLE_CIBLE_EXCEPTIONS,
)
from .plan_tarifaire import PlanTarifaire, Facteur
from .tables_mortalite  import (
    QX_TH0002, QX_TF0002, QX_INSEE_H, QX_INSEE_F,
    get_qx, construire_lx,
    calculer_annuite_viagere,
    calculer_annuite_viagere_prospective,
    insee_qx_prospectif,
    REFERENCE_REGLEMENTAIRE,
)

__all__ = [
    'BaseAgent', 'AuditTrail', 'AgentRafael',
    # Plan tarifaire — LA SOURCE UNIQUE du contrat A2→A3→conformité
    'PlanTarifaire', 'Facteur',
    # Conformité réglementaire — SOURCE UNIQUE pour les trois directions
    'filtrer_genre', 'filtrer_famille_cible',
    'COLS_GENRE_INTERDITES', 'COLS_GENRE_STEMS',
    'COLS_FAMILLE_CIBLE', 'COLS_FAMILLE_CIBLE_STEMS',
    'COLS_FAMILLE_CIBLE_EXCEPTIONS',
    'QX_TH0002', 'QX_TF0002', 'QX_INSEE_H', 'QX_INSEE_F',
    'get_qx', 'calculer_annuite_viagere',
    'calculer_annuite_viagere_prospective',
    'REFERENCE_REGLEMENTAIRE',
]
