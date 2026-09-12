"""
sp_scellement.py — un sceau qui scelle les résultats, et qui dit ce qu'il scelle.

LE DÉFAUT QUE CE MODULE FERME (D28)
Le hash de session de SP-AUDIT portait sur la liste des agents exécutés, leurs
`audit_id` — qui contiennent un horodatage — et trois chaînes de version. Les
**valeurs** des résultats n'y entraient jamais.

Mesuré le 12/09/2026, en trompant délibérément l'instrument :

    Best Estimate x 1000 ............ hash IDENTIQUE (4531576CD7A4E0D2)
    SCR x 1000 ..................... hash IDENTIQUE
    PM Rentes IP mise a 0 .......... hash IDENTIQUE
    MCR mis a 0 .................... hash IDENTIQUE
    les 7 RAG passes VERT -> ROUGE .. hash IDENTIQUE
    AUCUNE falsification, relance ... hash DIFFERENT (6938749449D61485)

L'instrument était donc insensible à ce qu'il prétendait sceller, et sensible à
ce qu'il devait ignorer. Un sceau qui change sans qu'aucun chiffre n'ait bougé
rend en outre *impossible* la démonstration qu'un rapport archivé correspond à
ses calculs : le recalcul de contrôle échouera toujours.

LE CHOIX D'ASSIETTE, ET POURQUOI IL EST INVERSÉ
Sceller une liste fermée de champs laisse hors du sceau tout champ qu'on a
oublié d'y mettre — et personne ne s'en aperçoit, puisque le sceau reste vert.
Ce module fait l'inverse : **il scelle tout, sauf ce qui est explicitement
déclaré non déterministe** (horodatages, durées d'exécution, chemins de
fichiers, graphiques). La liste des exclusions est courte et nommable ; la liste
des inclusions ne l'était pas.

Le sceau publie son périmètre. Un lecteur peut donc vérifier ce qui est couvert
au lieu de le supposer — c'est la moitié la plus importante de l'instrument.
"""
import hashlib
import json

__all__ = ["CLES_NON_DETERMINISTES", "empreinte_resultats", "PROFONDEUR_MAX"]

# Clés dont la valeur change d'une exécution à l'autre sans qu'aucun chiffre
# actuariel n'ait bouge. Les sceller rendrait le sceau instable, donc inutile.
CLES_NON_DETERMINISTES = frozenset({
    "audit_id",          # porte un horodatage
    "duree_sec",         # temps d'execution
    "timestamp",
    "date_generation",
    "horodatage",
    "graphiques",        # figures Plotly, volumineuses et non signifiantes
    "gph",
    "chemin",
    "chemin_fichier",
    "fichier",
    "narration",         # texte libre, peut venir d'un LLM
    "commentaire",       # idem
})

# Un resultat d agent est plat ou peu imbrique ; au-dela, on ne descend plus,
# pour qu un sceau reste calculable en temps borne.
PROFONDEUR_MAX = 4


def _scellable(valeur):
    """Types dont la valeur porte un sens actuariel reproductible."""
    return isinstance(valeur, (int, float, bool, str)) or valeur is None


def _normaliser(valeur):
    """Arrondit les flottants pour absorber le bruit de virgule flottante.

    Sans cela, deux exécutions identiques pourraient différer au 15e chiffre
    et faire changer le sceau — le défaut même que ce module corrige.
    """
    if isinstance(valeur, bool) or valeur is None:
        return valeur
    if isinstance(valeur, (int, float)):
        try:
            return round(float(valeur), 2)
        except (TypeError, ValueError, OverflowError):
            return str(valeur)
    return valeur


def _parcourir(objet, prefixe, scelle, perimetre, profondeur):
    """Aplatit récursivement en {chemin: valeur normalisée}."""
    if profondeur > PROFONDEUR_MAX:
        return

    if isinstance(objet, dict):
        for cle in sorted(objet, key=str):
            if str(cle) in CLES_NON_DETERMINISTES:
                continue
            _parcourir(objet[cle], "%s.%s" % (prefixe, cle) if prefixe else str(cle),
                       scelle, perimetre, profondeur + 1)
        return

    if isinstance(objet, (list, tuple)):
        for i, element in enumerate(objet):
            _parcourir(element, "%s[%d]" % (prefixe, i),
                       scelle, perimetre, profondeur + 1)
        return

    if _scellable(objet):
        scelle[prefixe] = _normaliser(objet)
        perimetre.append(prefixe)


def empreinte_resultats(resultats_agents, date_arrete="", versions=None):
    """Scelle les résultats publiés par les agents.

    Parameters
    ----------
    resultats_agents : dict
        {cle agent : resultat}. Les agents en échec sont ignorés : sceller
        une absence n'aurait pas de sens, et le rapport d'audit les signale
        déjà par ailleurs.
    date_arrete : str
        Donnée métier, et non horodatage d'exécution : deux recalculs du même
        arrêté doivent rendre le même sceau.
    versions : dict, optionnel
        Versions des tables et référentiels utilisés.

    Returns
    -------
    (str, list) : l'empreinte sur 16 caractères, et le périmètre scellé —
                  la liste triée des chemins effectivement couverts.
    """
    scelle, perimetre = {}, []

    for cle in sorted(resultats_agents or {}, key=str):
        resultat = resultats_agents[cle] or {}
        if not isinstance(resultat, dict) or not resultat.get("success"):
            continue
        _parcourir(resultat, str(cle), scelle, perimetre, 0)

    charge = {
        "resultats":   scelle,
        "date_arrete": date_arrete,
        "versions":    dict(sorted((versions or {}).items())),
    }
    texte = json.dumps(charge, sort_keys=True, ensure_ascii=False, default=str)
    empreinte = hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16].upper()
    return empreinte, sorted(perimetre)
