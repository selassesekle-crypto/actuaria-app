# =============================================================================
#  ActuarIA — A7 Ibrahim / N3
#  benktander.py — Benktander (1976), dit aussi Hovinen, ou « Gunnar Benktander »
# =============================================================================
#
#  LA FORMULE. Guide de l'Institut des Actuaires, février 2023, §2.c.iii. Elle
#  s'écrit de deux façons, qui coïncident exactement :
#
#      U_GB = α · U_CL + (1 − α) · U_BF          (mélange par crédibilité)
#      IBNR_GB = (1 − α) · U_BF                  (forme courte)
#
#  avec α = 1 / CDF, la fraction développée de l'année. L'équivalence tient
#  parce que U_CL = C / α, donc α · U_CL = C : le mélange revient à ajouter à
#  la charge connue une fraction (1 − α) de l'ultime BF. C'est la seconde
#  forme qui est implémentée ici — elle ne demande PAS les ultimes Chain
#  Ladder, donc n'introduit aucune dépendance nouvelle.
#
#  CE MODULE NE RECALCULE RIEN. `α` est le `pct_dev` déjà passé à
#  Bornhuetter-Ferguson, et `U_BF` est sa sortie `ultimates`. Benktander est
#  arithmétiquement une lecture de plus des mêmes nombres.
#
#  ┌───────────────────────────────────────────────────────────────────────┐
#  │  ⚠️ BENKTANDER N'ENTRE PAS DANS LE BEST ESTIMATE, ET NE DOIT JAMAIS   │
#  │  Y ENTRER.                                                            │
#  │                                                                       │
#  │  Il EST déjà un mélange de Chain Ladder et de Bornhuetter-Ferguson.   │
#  │  L'ajouter au vivier pondéré rouvrirait le défaut corrigé au commit   │
#  │  6e2e66e, où le point estimate de Mack VALAIT Chain Ladder et où les  │
#  │  deux étaient pondérés. Mesuré sur GenIns, α moyen = 0,7693 : avec    │
#  │  quatre méthodes à poids égaux, Chain Ladder pèserait RÉELLEMENT      │
#  │  44,2 % et Bornhuetter-Ferguson 30,8 %, pendant que le tableau        │
#  │  afficherait 25 % chacun. La duplication serait PARTIELLE et VARIABLE │
#  │  PAR ANNÉE — α dépend de la maturité — donc invisible à la lecture.   │
#  │                                                                       │
#  │  Verrouillé sur l'arbre syntaxique par `test_a7_benktander.py`, pas   │
#  │  par ce commentaire.                                                  │
#  └───────────────────────────────────────────────────────────────────────┘
#
#  CE QU'IL APPORTE, MESURÉ ET NON SUPPOSÉ. Mack (2000) montre que l'estimateur
#  a un MSE inférieur À LA FOIS à celui de Chain Ladder et à celui de BF sur
#  une plage de qualité de l'a priori. Campagne sur vérité connue, 300 tirages
#  par régime, erreur d'a priori ALÉATOIRE PAR ANNÉE — le seul cadre où un
#  mélange peut compenser :
#
#      dispersion a priori   bruit    err CL    err BF    err GB   gagnant
#                     10 %     6 %     2,99 %    3,07 %    2,83 %   GB
#                     35 %    20 %     9,98 %   10,47 %    9,53 %   GB
#                     50 %    40 %    20,06 %   18,28 %   18,20 %   GB
#      bilan sur 15 régimes : BF 8 · CL 4 · GB 3
#
#  Benktander l'emporte donc dans 3 régimes sur 15, de +0,08 à +0,45 point —
#  et exactement là où Chain Ladder et BF se valent, c'est-à-dire quand
#  l'erreur d'a priori et le bruit du triangle sont du même ordre. C'est la
#  prédiction de Mack, et c'est aussi sa limite : hors de cette bande, l'une
#  des deux méthodes de base fait mieux.
#
#  ⚠️ UNE CAMPAGNE ANTÉRIEURE CONCLUAIT « GB N'EST JAMAIS LE MEILLEUR ». Elle
#  appliquait un biais SYSTÉMATIQUE à l'a priori — or une combinaison convexe
#  est alors arithmétiquement condamnée à finir entre les deux, les erreurs
#  ayant le même signe. Le protocole invalidait sa propre conclusion.
#
#  AUCUN BLOC D'HYPOTHÈSES PROPRE. Benktander ne suppose rien de plus que ses
#  deux composantes : ses hypothèses sont l'union de CLM-H1..H4 (Chain Ladder)
#  et BFCC-H1..H6 (Bornhuetter-Ferguson), déjà construites et gatantes. Le
#  seul choix qui lui appartienne est celui de α = 1/CDF, qui n'est optimal
#  que dans la bande mesurée ci-dessus : c'est une MENTION informative, pas
#  une hypothèse à valider — cf. `MENTION_ALPHA`.
# =============================================================================

from typing import Dict, Optional

import numpy as np

#: Mention permanente sur le choix du facteur de crédibilité. Informative :
#: elle ne conditionne aucun résultat, elle dit ce que le chiffre vaut.
MENTION_ALPHA = (
    "Le facteur de crédibilité retenu est α = 1/CDF, celui de Benktander "
    "(1976). Il n'est proche de l'optimum que lorsque l'erreur de l'a priori "
    "et le bruit du triangle sont du même ordre : mesuré sur vérité connue, "
    "Benktander l'emporte sur Chain Ladder ET sur Bornhuetter-Ferguson dans "
    "3 régimes sur 15, de 0,08 à 0,45 point d'erreur. Hors de cette bande, "
    "l'une des deux méthodes de base fait mieux — l'écart entre Benktander et "
    "le Best Estimate retenu mesure donc la sensibilité du résultat à la "
    "pondération, il n'est pas une correction à lui apporter."
)

#: Au-delà, l'écart au Best Estimate est signalé : la pondération des méthodes
#: pèse alors autant que le choix des méthodes elles-mêmes.
SEUIL_ECART_SIGNALE = 0.10


def benktander(
    pct_dev:    np.ndarray,
    last_diag:  np.ndarray,
    resultat_bf: Optional[Dict],
    annee_base: int = 1,
) -> Dict:
    """Benktander (1976) — mélange Chain Ladder / BF par crédibilité.

    Parameters
    ----------
    pct_dev : fraction développée par année, c'est-à-dire α = 1/CDF. C'est
        EXACTEMENT le tableau passé à `bornhuetter_ferguson` : le même objet,
        pour que les deux méthodes ne puissent pas diverger sur α.
    last_diag : dernière valeur connue `C[i, k_i]`.
    resultat_bf : le dictionnaire rendu par `bornhuetter_ferguson`. Benktander
        se calcule SUR sa sortie ; il n'a donc ni exposition ni loss ratio à
        recevoir, et hérite mécaniquement de son indisponibilité.
    annee_base : première année comptée dans la réserve, comme partout en N3.

    Returns
    -------
    dict avec `disponible`, `ibnr_par_annee`, `ultimates`, `reserve_totale`,
    `alpha_par_annee`, `alpha_moyen`, `mention_alpha`, `message`, `alertes`.
    """
    n = len(last_diag)
    indispo = {
        'disponible':      False,
        'methode':         'Benktander (1976)',
        'ibnr_par_annee':  [0.0] * n,
        'ultimates':       [0.0] * n,
        'reserve_totale':  0.0,
        'alpha_par_annee': [],
        'alpha_moyen':     None,
        'mention_alpha':   MENTION_ALPHA,
        'alertes':         [],
    }

    # Benktander est une lecture de la sortie BF : sans BF, pas de Benktander.
    # Le motif est celui de `libelle_loss_ratio` — on ne fabrique pas un zéro
    # qui se lirait comme une réserve nulle.
    if not resultat_bf or not resultat_bf.get('disponible'):
        indispo['message'] = (
            "Benktander non calculée — elle se déduit de Bornhuetter-Ferguson, "
            "qui n'est pas disponible (mesure d'exposition ou charge ultime "
            "a priori absente)."
        )
        return indispo

    alpha  = np.asarray(pct_dev, dtype=float)
    dern   = np.asarray(last_diag, dtype=float)
    u_bf   = np.asarray(resultat_bf['ultimates'], dtype=float)
    if not (len(alpha) == len(dern) == len(u_bf) == n):
        indispo['message'] = (
            f"Benktander non calculée — tailles incohérentes "
            f"(α {len(alpha)}, diagonale {len(dern)}, ultimes BF {len(u_bf)})."
        )
        return indispo

    # ── La formule, dans sa forme courte ─────────────────────────────────────
    #  IBNR_GB = (1 − α) · U_BF, puis U_GB = charge connue + IBNR_GB.
    #  `pct_dev` est écrêté à [0,1] en amont : la fraction à venir ne peut donc
    #  pas être négative, exactement comme dans Bornhuetter-Ferguson dont
    #  Benktander est une relecture. Les reprises restent portées par Chain
    #  Ladder, conformément au chantier IBNR négatif.
    frac_a_venir = 1.0 - alpha
    ibnr         = frac_a_venir * u_bf
    ultimates    = dern + ibnr
    reserve      = float(np.sum(ibnr[annee_base:]))
    alpha_moyen  = float(np.mean(alpha[annee_base:])) if n > annee_base else None

    alertes = []
    if alpha_moyen is not None and alpha_moyen > 0.99:
        alertes.append(
            "⚠️ Benktander : α moyen = {:.4f}, le portefeuille est presque "
            "entièrement développé — l'estimateur coïncide alors avec Chain "
            "Ladder et n'apporte aucune information propre.".format(alpha_moyen)
        )

    return {
        'disponible':      True,
        'methode':         'Benktander (1976)',
        'ibnr_par_annee':  [round(float(v), 2) for v in ibnr],
        'ultimates':       [round(float(v), 2) for v in ultimates],
        'reserve_totale':  round(reserve, 2),
        'alpha_par_annee': [round(float(v), 6) for v in alpha],
        'alpha_moyen':     round(alpha_moyen, 6) if alpha_moyen is not None else None,
        'mention_alpha':   MENTION_ALPHA,
        'source_apriori':  resultat_bf.get('source_lr', ''),
        'message': (
            "Benktander = {:.0%} Chain Ladder + {:.0%} Bornhuetter-Ferguson "
            "en moyenne (α = 1/CDF, par année) — réserve {} €."
            # Le separateur de milliers est applique au SEUL nombre :
            # `.replace()` sur la phrase entiere lui mangerait ses propres
            # virgules -- le defaut s'est produit quatre fois dans les lots
            # precedents, toujours dans un message d'affichage.
            .format(alpha_moyen or 0.0, 1.0 - (alpha_moyen or 0.0),
                    '{:,.0f}'.format(reserve).replace(',', ' '))
        ),
        'alertes': alertes,
    }


def ecart_au_best_estimate(reserve_gb: float, best_estimate: float) -> Dict:
    """Écart relatif de Benktander au Best Estimate retenu, et son verdict.

    C'est le seul usage décisionnel de Benktander dans A7 : il ne corrige pas
    le Best Estimate, il mesure à quel point celui-ci dépend de la pondération
    entre méthodes. Un écart large ne dit pas que le BE est faux — il dit que
    le choix des poids pèse autant que le choix des méthodes.
    """
    if not best_estimate:
        return {'ecart_pct': None, 'signale': False, 'commentaire':
                "Écart non calculable — Best Estimate nul ou absent."}
    ecart = reserve_gb / best_estimate - 1.0
    signale = abs(ecart) > SEUIL_ECART_SIGNALE
    return {
        'ecart_pct': round(ecart * 100, 2),
        'signale':   signale,
        'commentaire': (
            "Benktander s'écarte de {:+.1f} % du Best Estimate retenu. "
            "{}".format(
                ecart * 100,
                "Au-delà de {:.0%}, la pondération entre méthodes pèse autant "
                "que leur choix : à documenter dans le rapport."
                .format(SEUIL_ECART_SIGNALE) if signale else
                "L'écart reste dans la plage où la pondération n'est pas "
                "déterminante.")
        ),
    }


def lignes_benktander_rapport(n3: Dict, n4: Optional[Dict] = None) -> list:
    """Les lignes d'affichage de Benktander — SOURCE UNIQUE pour les 3 formats.

    HTML, Word et Excel lisent CETTE fonction. Le motif vient du lot Munich,
    ou trois formats rendaient trois choses differentes de la meme methode
    parce que chacun refaisait la mise en forme.

    Renvoie une liste de couples (libelle, valeur) prets a afficher.
    """
    gb = (n3 or {}).get('benktander') or {}
    if not gb.get('disponible'):
        return [("Benktander (1976)",
                 gb.get('message', "Non calculee — cf. Bornhuetter-Ferguson."))]

    a = gb.get('alpha_moyen') or 0.0
    lignes = [
        ("Réserve Benktander", '{:,.0f} €'.format(gb['reserve_totale'])
                               .replace(',', '\u202f')),
        ("Facteur de crédibilité α moyen", '{:.4f}'.format(a)),
        ("Composition moyenne",
         "{:.0%} Chain Ladder + {:.0%} Bornhuetter-Ferguson".format(a, 1.0 - a)),
    ]
    be = (n4 or {}).get('best_estimate')
    if be:
        ec = ecart_au_best_estimate(gb['reserve_totale'], float(be))
        lignes.append(("Écart au Best Estimate retenu",
                       "{:+.2f} %{}".format(ec['ecart_pct'],
                                            "  ⚠️ à documenter" if ec['signale']
                                            else "")))
    lignes.append(("Portée", "INFORMATIVE — Benktander n'entre pas dans le "
                             "Best Estimate : il en est déjà un mélange."))
    lignes.append(("Choix de α", gb.get('mention_alpha', MENTION_ALPHA)))
    for alerte in gb.get('alertes', ()):
        lignes.append(("Alerte", alerte))
    return lignes
