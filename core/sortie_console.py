"""
=============================================================================
  ActuarIA — LE RENDU CONSOLE NE DOIT JAMAIS FAIRE ÉCHOUER UN CALCUL
=============================================================================

⚠️⚠️ MESURÉ LE 10/09/2026, SUR LA CHAÎNE RÉELLE. Le même code, les mêmes
données, deux verdicts :

    console utf-8   ->  A3 success = True    statut = VERT
    console cp1252  ->  A3 success = False   statut = ROUGE
    'charmap' codec can't encode characters in position 1-65

`cp1252` est l'encodage par défaut d'une console Windows française. Les agents
affichent `€`, `→`, `═`, `β` ; l'affichage vit **à l'intérieur du `try` métier**
de `run()` — vérifié par AST sur A3, A4 et A5. Un incident de RENDU devient
donc un échec de CALCUL, et le statut RAG publié bascule.

LA CASCADE COMPLÈTE, TELLE QUE L'AUDIT L'A RELEVÉE
  A3, A4 et A5 rendent `success: False` · A6 échoue sur « Aucun résultat
  disponible » et rend `_erreur`, dont `branche` vaut `None` ·
  `branche.replace(...)` lève · **le rapport HTML signé n'est pas produit du
  tout**. Et le Word d'A4 disparaît sous un « échoué (non bloquant) ».

⚠️⚠️ ET L'INSTRUMENT DE PREUVE EST ATTEINT. `TestAssietteDeLaChaine` porte
`GEL-12` et `GEL-13` — « l'assiette couvre TOUTE la chaîne ». Sous cp1252 il
n'exécute **aucune assertion** et se déclare en échec : `Ran 0 · FAILED`.
*Tant que ce défaut tient, tout « aucun euro n'a bougé » ne vaut que pour
l'encodage de la console qui l'a mesuré.*

POURQUOI `errors='replace'` ET PAS UN SIMPLE `try/except`
  Sur une console cp1252, « 1 025 EUR » devient « 1 025 ? » et **le rapport
  reste lisible**. Un `try/except` autour de l'appel l'aurait tronqué à la
  première ligne fautive : on perdrait le rapport pour sauver le calcul.

⚠️ ET LE FILET NE S'ÉLARGIT PAS. Seule `UnicodeEncodeError` est rattrapée.
L'étendre à `Exception` ferait disparaître une vraie panne de rendu dans le
même silence — la faute que ce module existe pour défaire, à l'envers.
=============================================================================
"""

from __future__ import annotations

import contextlib
import sys

__all__ = ['afficher_sans_echouer', 'console_tolerante']


@contextlib.contextmanager
def console_tolerante(flux=None):
    """Rend le flux tolérant aux caractères qu'il ne sait pas coder.

    ⚠️⚠️ ON LIT `errors` AVANT DE LE CHANGER, ET ON LE REMET DANS UN `finally`.
    Un contexte qui ne restaure pas laisse le processus dans un état que
    personne n'a demandé — et le prochain appelant hériterait d'un flux
    silencieusement permissif.

    ⚠️ UN FLUX NON RECONFIGURABLE N'EST PAS UNE ERREUR. Un `StringIO`, un pipe
    capturé, un flux déjà fermé : on ne fait rien, et `afficher_sans_echouer`
    garde alors le second filet.
    """
    flux = sys.stdout if flux is None else flux
    reconfigurer = getattr(flux, 'reconfigure', None)
    ancien = getattr(flux, 'errors', None)
    change = False
    if callable(reconfigurer) and ancien not in ('replace', 'backslashreplace'):
        try:
            reconfigurer(errors='replace')
            change = True
        except (ValueError, OSError, AttributeError):
            change = False
    try:
        yield
    finally:
        if change:
            try:
                reconfigurer(errors=ancien or 'strict')
            except (ValueError, OSError, AttributeError):
                pass


def afficher_sans_echouer(rendu, journal=None, contexte='') -> bool:
    """Exécute un rendu console sans qu'il puisse faire échouer le calcul.

    ⚠️⚠️ SEULE `UnicodeEncodeError` EST RATTRAPÉE, ET C'EST LE POINT. Élargir
    ce filet à `Exception` ferait disparaître une vraie panne du rendu dans le
    même silence — exactement la faute que ce module défait, retournée.

    ⚠️ ET L'ÉCHEC SE DIT AU JOURNAL. Un rendu perdu sans un mot laisserait
    l'actuaire croire que l'agent n'avait rien à afficher.

    Rend `True` si le rendu est allé au bout, `False` s'il a été rattrapé.
    """
    with console_tolerante():
        try:
            rendu()
            return True
        except UnicodeEncodeError as erreur:
            if journal is not None:
                journal.warning(
                    "[%s] Rapport console NON AFFICHE (%s) : le CALCUL n'est "
                    "pas affecte.", contexte, erreur)
            return False
