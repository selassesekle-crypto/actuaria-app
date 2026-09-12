"""
sp_console.py — la sortie console ne peut plus détruire un calcul.

LE DÉFAUT QUE CE MODULE FERME (D35)
Les sept agents de calcul de la direction — S1, S2, S3, P1, P2, P3, P4 — écrivent
leur trace avec `print()`, et ces traces contiennent des caractères hors du jeu
latin-1 : ✅, →, ≥, ±, les émojis de statut. Sur une console Windows française,
dont l'encodage par défaut est `cp1252`, le premier de ces caractères lève
`UnicodeEncodeError`. L'exception remonte jusqu'au `try` général de `run()`, qui
la convertit en `success=False` : **le calcul entier est perdu, et aucun document
n'est produit**, alors que rien n'était faux dans les chiffres.

Mesuré le 12/09/2026 : sous `PYTHONIOENCODING=cp1252` et sous `ascii`, les sept
agents rendent `success=False`. Les dix autres modules de la direction passent
par `self.logger` et y échappent. Le message rendu à l'utilisateur parle de codec,
jamais d'encodage de console : il est introuvable pour qui cherche une erreur de
données.

CE QUE CE MODULE NE FAIT PAS
Il ne change aucune valeur calculée. Une trace non représentable est affichée avec
un caractère de remplacement ; le nombre, lui, est intact. Une sortie console est
un confort de lecture, jamais une donnée — et elle ne doit jamais pouvoir faire
échouer ce qu'elle décrit.

TROIS USAGES, ET POURQUOI LES TROIS
  tracer()            — remplace `print` dans les sept agents. C'est la protection
                        qui compte : elle agit AU MOMENT DE L'ÉCRITURE, donc elle
                        tient même si `sys.stdout` a été remplacé après coup.
  securiser_sortie()  — à appeler une fois au chargement de la direction. Couvre
                        d'un coup tout ce qui n'est pas passé par `tracer`, dont
                        les traces des fichiers de test.
  ecrire_console()    — pour un site d'appel qui veut garder la main sur son flux
                        et savoir si sa trace a été dégradée.

⚠️ Mesuré le 12/09/2026 : `securiser_sortie()` SEULE ne suffit pas. Elle agit au
chargement, sur le flux existant à cet instant ; un `sys.stdout` substitué plus
tard — capture de pytest, redirection, interface graphique — n'est pas couvert.
C'est précisément pour cela que `tracer` protège à l'écriture et non à l'import.
Les deux sont conservés : ils ne couvrent pas la même surface.
"""
import sys

__all__ = ["tracer", "securiser_sortie", "ecrire_console", "sortie_sure",
           "repertoire_demonstration"]


def tracer(*valeurs, sep=" ", end="\n", file=None, flush=False):
    """Écrit une trace comme `print`, mais ne lève jamais sur l'encodage.

    Signature identique à `print` : c'est un remplacement direct, et c'est
    voulu — les sept agents contenaient 153 appels, qu'il aurait été à la fois
    plus long et plus risqué de réécrire un par un.

    Le flux est résolu À CHAQUE APPEL, jamais mémorisé : une trace reste donc
    protégée même si `sys.stdout` est remplacé après le chargement du module.
    """
    flux = file if file is not None else sys.stdout
    if flux is None:
        return
    texte = sep.join(str(v) for v in valeurs) + end
    try:
        flux.write(texte)
    except (UnicodeEncodeError, UnicodeError, ValueError, OSError):
        encodage = getattr(flux, "encoding", None) or "utf-8"
        try:
            flux.write(texte.encode(encodage, errors="replace")
                            .decode(encodage, errors="replace"))
        except Exception:
            # Une trace perdue ne justifie jamais de faire echouer le calcul
            # qu elle decrit. C est tout l objet de ce module.
            pass
    if flush:
        try:
            flux.flush()
        except Exception:
            pass

# Encodages qui ne peuvent pas représenter les caractères de trace du module.
_ENCODAGES_ETROITS = ("cp1252", "windows-1252", "latin-1", "iso-8859-1", "ascii")


def _deja_tolerant(flux):
    """Vrai si le flux remplace déjà les caractères qu'il ne sait pas encoder."""
    return getattr(flux, "errors", None) in ("replace", "backslashreplace", "ignore")


def securiser_sortie(flux=None):
    """Rend une écriture console incapable de lever, pour tout le processus.

    N'altère NI l'encodage NI le contenu : seul le mode d'erreur passe à
    « replace », de sorte qu'un caractère non représentable s'affiche en
    substitut au lieu d'interrompre le calcul.

    Parameters
    ----------
    flux : file-like, optionnel
        Flux à sécuriser. Par défaut, `sys.stdout` et `sys.stderr`.

    Returns
    -------
    dict : {nom du flux : état}, où l'état vaut 'securise', 'deja_tolerant'
           ou 'impossible'. Le retour est explicite pour qu'un appelant — ou
           un test — puisse vérifier ce qui a réellement été fait, plutôt que
           de le supposer.
    """
    cibles = [("flux", flux)] if flux is not None else [
        ("stdout", sys.stdout), ("stderr", sys.stderr)]

    etat = {}
    for nom, f in cibles:
        if f is None:
            etat[nom] = "impossible"
            continue
        if _deja_tolerant(f):
            etat[nom] = "deja_tolerant"
            continue
        try:
            f.reconfigure(errors="replace")
            etat[nom] = "securise"
        except (AttributeError, ValueError, OSError):
            # Flux sans reconfigure (capture pytest, StringIO, pipe ferme) :
            # ecrire_console() reste la voie sure pour ces cas-la.
            etat[nom] = "impossible"
    return etat


def ecrire_console(lignes, flux=None):
    """Écrit des lignes sans jamais lever sur un problème d'encodage.

    Parameters
    ----------
    lignes : str | iterable de str
        Une ligne ou une suite de lignes. Le retour à la ligne est ajouté.
    flux : file-like, optionnel
        Par défaut `sys.stdout`.

    Returns
    -------
    int : nombre de lignes écrites en substitution (0 si tout est passé tel quel).
          Un appelant qui veut savoir si sa trace a été dégradée peut le lire.
    """
    if isinstance(lignes, str):
        lignes = [lignes]
    flux = flux if flux is not None else sys.stdout
    encodage = getattr(flux, "encoding", None) or "utf-8"

    degradees = 0
    for ligne in lignes:
        texte = ligne if isinstance(ligne, str) else str(ligne)
        try:
            flux.write(texte + "\n")
        except (UnicodeEncodeError, UnicodeError, ValueError, OSError):
            try:
                flux.write(texte.encode(encodage, errors="replace")
                                .decode(encodage, errors="replace") + "\n")
                degradees += 1
            except Exception:
                # Dernier recours : une trace perdue ne justifie jamais
                # de faire echouer le calcul qu elle decrit.
                degradees += 1
    return degradees


def sortie_sure(encodage=None):
    """Vrai si le flux courant peut représenter les caractères de trace.

    Sert aux tests et aux diagnostics : permet d'affirmer « la console est
    étroite » sur une mesure, et non sur une supposition.
    """
    enc = encodage or getattr(sys.stdout, "encoding", None) or "utf-8"
    return enc.lower().replace("_", "-") not in _ENCODAGES_ETROITS


def repertoire_demonstration(code_agent):
    r"""Répertoire d'écriture des blocs de démonstration `__main__`.

    LE DÉFAUT FERMÉ (D15)
    Les sept blocs de démonstration écrivaient dans des chemins POSIX
    littéraux — `/tmp/p1/models`, `/tmp/p4/audit`. Sous Windows ces chemins
    ne sont pas invalides : ils se résolvent en `C:\tmp\...`, un répertoire
    créé à la RACINE DU DISQUE, hors de tout ménage. Mesuré le 12/09/2026 :
    `C:\tmp` contenait **92 707 fichiers pour 117,9 Mo** — dont la quasi-
    totalité vient d'une autre direction, mais le mécanisme est identique ici.

    `p4_reporting` portait en plus un `sys.path.insert(0, '/home/claude')` :
    un chemin de machine de développement, en TÊTE du chemin de recherche,
    donc prioritaire sur le dépôt lui-même. Inerte sous Windows puisque le
    répertoire n'existe pas — mais le dépôt est public, et sur une machine où
    ce répertoire existe, un module homonyme y serait chargé à la place du vrai.

    Cette fonction rend un répertoire temporaire RÉEL, celui que le système
    d'exploitation désigne, sous un nom qui dit à quoi il sert.
    """
    import tempfile
    from pathlib import Path

    chemin = Path(tempfile.gettempdir()) / ("actuaria_demo_%s" % code_agent)
    chemin.mkdir(parents=True, exist_ok=True)
    return chemin
