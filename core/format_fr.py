# -*- coding: utf-8 -*-
"""T3 — la convention française de présentation des nombres, en un seul endroit.

⚠️ POURQUOI CE MODULE EXISTE. Le dépôt porte **quinze fichiers** qui définissent
chacun leur `_f` / `_pct` — trente définitions au total. Mesuré sur la même
entrée, elles rendent **trois résultats différents** :

    _f(18 680 856, 0)
      A7 + les 2 agents SP + les 2 services SP  →  '18 680 856 €'  (U+202F avant €)
      tarification + les 6 `m_rapport_*`        →  '18 680 856 €'  (ESPACE ORDINAIRE)
      les 3 rapports Vie/EP-RE                  →  idem A7…

    …mais _f(0.1775, 4)
      Vie/EP-RE                                 →  '0.1775 €'   ⚠️ un Gini en euros

⚠️ LA DIFFÉRENCE INVISIBLE EST LA PLUS COÛTEUSE. Une espace ORDINAIRE entre le
nombre et « € » autorise une coupure de ligne : le montant peut se retrouver
scindé sur deux lignes d'un rapport signé. C'est précisément ce que l'espace
fine INSÉCABLE (U+202F) empêche, et c'est pour cela qu'A7 l'emploie.

CE MODULE REPREND LA CONVENTION D'A7 — il n'en invente pas une seizième. Il y
ajoute le seul cas qu'A7 ne couvre pas : un nombre SANS unité. `_f(v, 0)` d'A7
suffixe « € », ce qui est faux pour un effectif ou un nombre de modèles.

⚠️ ET LE SÉPARATEUR DÉCIMAL RESTE LE POINT, COMME A7 — ce n'est PAS un oubli.
La convention française voudrait la virgule, et la narration de Claude l'écrit
déjà ainsi (« 0,1775 »). Mais la changer ici ne réglerait rien : elle est en
dur dans quatorze autres fichiers, sur trois directions, tous producteurs de
livrables signés. Passer la virgule à un seul endroit créerait une divergence
de plus au lieu d'en supprimer une. La question est ouverte et se traite pour
tout le dépôt à la fois — pas dans le lot d'un seul rapport.
"""
from typing import Any, Optional

# L'espace fine INSÉCABLE : elle sépare les milliers, et elle attache l'unité
# à son nombre. C'est le seul séparateur admis ici.
SEP_MILLIERS = ' '

# ⚠️ CE QUI N'EST PAS CALCULABLE N'EST PAS ZÉRO. Toute la famille rend ce
# tiret, jamais « 0 » : un zéro affirme une valeur, un tiret avoue une absence.
ABSENT = '—'

# Le point décimal, hérité d'A7 — voir la réserve en tête de module.
SEP_DECIMAL = '.'


def _fini(valeur: Any) -> Optional[float]:
    """La valeur en flottant si elle est réelle et finie, sinon None."""
    if valeur is None:
        return None
    try:
        f = float(valeur)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float('inf') else None


def _groupe(f: float, dec: int) -> str:
    """Le nombre groupé par milliers, sans unité."""
    return f'{f:,.{dec}f}'.replace(',', SEP_MILLIERS)


def nombre(valeur: Any, dec: int = 0) -> str:
    """Un nombre SANS unité : effectif, Gini, ratio, nombre de modèles.

    ⚠️ C'EST LE CAS QU'A7 NE COUVRE PAS. Son `_f(v, 0)` suffixe « € » ;
    l'appliquer à « 7 modèles comparés » donnerait « 7 € ».
    """
    f = _fini(valeur)
    return ABSENT if f is None else _groupe(f, dec)


def euros(valeur: Any, dec: int = 0) -> str:
    """Un montant. L'unité est attachée par une espace INSÉCABLE."""
    f = _fini(valeur)
    return ABSENT if f is None else _groupe(f, dec) + SEP_MILLIERS + '€'


def pourcent(valeur: Any, dec: int = 1) -> str:
    """Un pourcentage, la valeur étant DÉJÀ en points de pourcentage."""
    f = _fini(valeur)
    return ABSENT if f is None else _groupe(f, dec) + SEP_MILLIERS + '%'


def tronque(texte: Any, largeur: int) -> str:
    """Coupe un texte trop long SUR UN MOT, et le dit par des points de suite.

    ⚠️ LE RAPPORT COUPAIT EN PLEIN MOT, SANS RIEN DIRE. Un conseil actuariel
    s'achevait sur « le GLM est bien spécifié sur toute », une note sur
    « ...4 dimensions normalisées (Gini, Stabilité, Interprétabilité, RMSE).
    N'es ». Le lecteur ne pouvait pas savoir qu'il manquait quelque chose : la
    phrase semblait mal écrite, pas tronquée.
    """
    t = '' if texte is None else str(texte).strip()
    if len(t) <= largeur:
        return t
    coupe = t[:largeur].rsplit(' ', 1)[0].rstrip(' ,;:.')
    return (coupe or t[:largeur]) + '…'


# ── Le nombre de décimales par NATURE de grandeur ────────────────────────────
# ⚠️ UNE PRÉCISION SE JUSTIFIE, ELLE NE SE CHOISIT PAS AU CAS PAR CAS. Le
# rapport mesuré affichait la même colonne à 1, 3 et 4 décimales selon la
# ligne — « 1.0 » à côté de « 1.2176 ».
DEC_GINI = 4          # convention du dépôt : un Gini se lit à 4 décimales
DEC_RATIO = 3         # surapprentissage, A/E : 3 suffisent à décider
DEC_POURCENT = 1      # un pourcentage de rapport se lit à la décimale
DEC_EFFECTIF = 0      # un contrat ne se compte pas en fractions
