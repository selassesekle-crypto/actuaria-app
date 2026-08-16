# =============================================================================
#  ActuarIA — Direction Non-Vie / Service Data
#  Construction et qualification des données pour tous les agents Non-Vie
#  ⚠️ CET EN-TÊTE LISTAIT TROIS MODULES QUI N'EXISTENT PAS — `nv_triangle_
#  builder` (supprimé avec l'ancien chemin), `nv_large_loss` et
#  `nv_data_quality` (jamais présents dans ce paquet). Il décrivait donc un
#  paquet imaginaire. La liste ci-dessous est celle des fichiers réels.
#
#  · nv_triangle           : LA FAÇADE — orchestre les six modules ci-dessous
#  · nv_triangle_io        : lecture universelle (csv, excel, json, parquet)
#  · nv_triangle_mapping   : colonnes source → vocabulaire canonique
#  · nv_triangle_mapping_llm : proposition de mapping ; l'actuaire valide
#  · nv_triangle_construction : cumulé / incrémental / données individuelles
#  · nv_triangle_separation : grands sinistres / attritionnels (seuil LLT)
#  · nv_triangle_diagnostics : score de santé du triangle, 7 contrôles
#  · nv_triangle_negatifs  : signale les négatifs, n'en transforme aucun
#  · nv_triangle_projection : ultimes et IBNR — source unique de la projection
# =============================================================================
