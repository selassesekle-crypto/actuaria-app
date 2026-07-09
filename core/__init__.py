# ActuarIA — core
# Modules transversaux communs à tous les agents
from .base_agent        import BaseAgent
from .audit_trail       import AuditTrail, AgentRafael
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
    'QX_TH0002', 'QX_TF0002', 'QX_INSEE_H', 'QX_INSEE_F',
    'get_qx', 'calculer_annuite_viagere',
    'calculer_annuite_viagere_prospective',
    'REFERENCE_REGLEMENTAIRE',
]
