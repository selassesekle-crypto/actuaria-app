"""
direction_vie_epre/services/tables_mortalite_officielles.py
============================================================
Wrapper de compatibilite — reexporte depuis core.tables_mortalite.
Source unique de verite : core/tables_mortalite.py

Usage (inchange pour V1, V2, EP1, EP2) :
    from direction_vie_epre.services.tables_mortalite_officielles import (
        QX_TH0002, QX_TF0002, get_qx, calculer_annuite_viagere,
        calculer_annuite_viagere_prospective, REFERENCE_REGLEMENTAIRE,
    )
"""

from core.tables_mortalite import (  # noqa: F401
    QX_TH0002,
    QX_TF0002,
    QX_INSEE_H,
    QX_INSEE_F,
    TABLES_DISPONIBLES,
    REFERENCE_REGLEMENTAIRE,
    REFERENCE_INSEE,
    get_qx,
    construire_lx,
    calculer_annuite_viagere,
    calculer_probabilite_survie,
    calculer_annuite_viagere_prospective,
    insee_qx_prospectif,
)

__all__ = [
    "QX_TH0002", "QX_TF0002", "QX_INSEE_H", "QX_INSEE_F",
    "TABLES_DISPONIBLES", "REFERENCE_REGLEMENTAIRE", "REFERENCE_INSEE",
    "get_qx", "construire_lx", "calculer_annuite_viagere",
    "calculer_probabilite_survie", "calculer_annuite_viagere_prospective",
    "insee_qx_prospectif",
]
