"""
core/derivations.py — LA RELATION DÉRIVÉE → SOURCE(S) BRUTE(S).

Source unique du lien entre une colonne DÉRIVÉE (calculée par A2 dans
`_calculer_indicateurs_derives`) et la/les colonne(s) BRUTE(s) que le fichier
client doit fournir. Trois consommateurs, UNE seule vérité :

  · A2._sources_brutes  → message de `valider_contre` (nommer la source que le
    client peut fournir — kilometrage_annuel — pas la dérivée km_par_an_normalise) ;
  · PlanTarifaire.colonnes_attendues() → ce que le fichier client doit livrer
    (référentiel des colonnes d'ENTRÉE, en noms de source brute) ;
  · core.mapping_client → cibles de mapping valides + couverture (futures amputées).

POURQUOI DANS core/ (et pas dans A2) : le plan et le moteur de mapping doivent y
accéder SANS dépendre d'un agent. A2 garde son `DATA_DICTIONNAIRE` riche
(justification / opération / usage — traçabilité ACPR §3.2) ; la RELATION, elle,
est ici. ⚠ `DATA_DICTIONNAIRE` ne documente que 3 des 9 dérivées : cette table est
DÉLIBÉRÉMENT plus complète. Un test de cohérence vérifie l'accord sur les 3
communes ET l'accord de la table avec le comportement réel de
`_calculer_indicateurs_derives` (garde par présence des sources).

AUTEUR : ActuarIA
"""
from typing import Dict, List, Sequence, Tuple

__all__ = ["DERIVATIONS", "sources_brutes"]

# dérivée → sources BRUTES. Miroir EXACT de a2._calculer_indicateurs_derives.
# Récursif : logement_ancien → age_logement → annee_construction. `exposition`
# apparaît comme source (km_par_an_normalise) mais reste une colonne OBLIGATOIRE du
# plan — jamais une source « amputable ».
DERIVATIONS: Dict[str, Tuple[str, ...]] = {
    "risque_historique":   ("bonus_malus", "antecedents_sinistres_n1"),
    "km_par_an_normalise": ("kilometrage_annuel", "exposition"),
    "jeune_conducteur":    ("age",),
    "senior_conducteur":   ("age",),
    "vehicule_recent":     ("age_vehicule",),
    "vehicule_ancien":     ("age_vehicule",),
    "valeur_par_m2":       ("valeur_mobilier", "surface_m2"),
    "age_logement":        ("annee_construction",),
    "logement_ancien":     ("age_logement",),      # récursif → annee_construction
}


def sources_brutes(colonnes: Sequence[str]) -> List[str]:
    """Traduit des colonnes (dérivées OU brutes) vers leur(s) source(s) BRUTE(s).

    Une colonne absente de DERIVATIONS est déjà une source brute → laissée telle
    quelle. Récursif (logement_ancien → age_logement → annee_construction), ordre
    d'apparition préservé, dédupliqué.
    """
    resolues: List[str] = []
    for c in colonnes:
        srcs = DERIVATIONS.get(c)
        if srcs:
            resolues.extend(sources_brutes(srcs))
        else:
            resolues.append(c)
    vu = set()
    return [x for x in resolues if not (x in vu or vu.add(x))]
