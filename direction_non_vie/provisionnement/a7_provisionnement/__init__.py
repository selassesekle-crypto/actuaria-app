# =============================================================================
#  ActuarIA — Agent A7 Ibrahim v5.0
#  __init__.py  —  Interface publique du package a7_provisionnement
# =============================================================================
#
#  Import unique depuis actuaria_app.py (inchangé vs v4.0) :
#
#      from a7_provisionnement import AgentA7Provisionnement
#
# =============================================================================

from .agent import AgentA7Provisionnement

__all__ = ['AgentA7Provisionnement']
__version__ = '5.0.0'
