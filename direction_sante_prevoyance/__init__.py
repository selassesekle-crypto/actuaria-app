"""
Direction Santé-Prévoyance

Le chargement de la direction sécurise la sortie console avant toute autre chose.

POURQUOI ICI, ET POURQUOI INCONDITIONNELLEMENT
Les sept agents de calcul tracent leur déroulé avec `print()`, et ces traces
portent des caractères hors latin-1 (✅, →, ≥, ±). Sur une console Windows
française — `cp1252`, la configuration la plus probable chez un assureur — le
premier de ces caractères levait `UnicodeEncodeError`, l'exception remontait au
`try` général de `run()`, et le calcul entier était perdu : `success=False`,
aucun document produit, pour une raison qui n'avait rien à voir avec les chiffres.

Le corriger au niveau du paquet plutôt qu'aux 188 sites d'appel a trois vertus :
une seule ligne au lieu de 188 modifications, aucune trace oubliée, et la
protection s'étend aux fichiers de test, qui écrivent eux aussi sur la console.

L'appel ne modifie ni l'encodage ni aucune valeur calculée : il change seulement
le mode d'erreur du flux, pour qu'un caractère non représentable s'affiche en
substitut au lieu d'interrompre ce qu'il décrit.
"""
try:
    from .services.sp_console import securiser_sortie as _securiser_sortie

    _ETAT_CONSOLE = _securiser_sortie()
except Exception:  # pragma: no cover - un garde-fou ne doit jamais bloquer
    # Si le garde-fou lui-même ne peut pas se charger, la direction doit
    # continuer à fonctionner : on le signale sans rien interrompre.
    _ETAT_CONSOLE = {"stdout": "indisponible", "stderr": "indisponible"}
