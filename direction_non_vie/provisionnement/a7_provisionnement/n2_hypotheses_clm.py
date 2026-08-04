# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n2_hypotheses_clm.py  —  Hypothèses PROPRES à Chain Ladder / Mack
#
#  Rôle
#  ----
#  Vérifier les hypothèses que Chain Ladder et Mack posent RÉELLEMENT, telles
#  que le Guide de l'Institut des Actuaires (février 2023) les énonce §3.b.i
#  (p25-26) et les met en œuvre dans son annexe 9.d (p80-83).
#
#      CLM-H1  indépendance des années de survenance  (effet calendaire)
#      CLM-H2  existence des facteurs de développement (moment d'ordre 1)
#      CLM-H3  structure de variance                   (moment d'ordre 2)
#      CLM-H4  incertitude de la queue de développement — HORS GUIDE, cf. infra
#
#  Chain Ladder repose sur H1 + H2. Mack ajoute H3 (son apport propre est la
#  volatilité) et, dès qu'une queue est appliquée, H4.
#
#  PÉRIMÈTRE DE CE MODULE — il PRODUIT des verdicts, il n'en TIRE aucune
#  conséquence. Aucune méthode n'est exclue, aucun poids n'est modifié, aucun
#  score n'est calculé ici. Le champ `critique_pour` est DESCRIPTIF : il dit ce
#  que la théorie invalide, il n'est branché sur rien. Ce que le système fera de
#  ces verdicts relève de la gouvernance (étape 3 du plan) et n'est pas traité.
#
#  ⚠️ CE MODULE NE REMPLACE PAS `n2_hypotheses.py`, il vit À CÔTÉ. Le cadre
#  H1-H4 historique continue de piloter les scores et la sélection des méthodes.
#
#  ─────────────────────────────────────────────────────────────────────────────
#  D'OÙ VIENNENT LES SEUILS — distinction NON NÉGOCIABLE
#
#  · CLM-H1 : le seuil vient DU GUIDE. « Pour un niveau de confiance à 95 %,
#    l'hypothèse est rejetée car la statistique de test est en dehors de
#    l'intervalle [−1,96 ; 1,96] » (annexe 9.d, p82).
#  · CLM-H2, CLM-H3 : LE GUIDE NE DONNE AUCUN SEUIL. Il montre un R² de 0,9817
#    sans le commenter (p83) et demande, pour la variance, que les résidus
#    « ne montrent pas de tendance spécifique » — sans test formel. Tous les
#    seuils de ce module pour H2 et H3 sont donc NOTRE JUGEMENT, signalés comme
#    tels dans chaque résultat via le champ `source_critere`.
#  · CLM-H4 : n'existe pas dans le guide. Construction propre, cf. sa docstring.
#
#  ─────────────────────────────────────────────────────────────────────────────
#  COQUILLES DU GUIDE CORRIGÉES (CLM-H1)
#
#  L'annexe 9.d écrit `c_i = C(i−1, ⌊(i−1)/2⌋) × n_i/2^{n_i}` et
#  `Var(Z_i) = n_i×(i−1)/4 − …`, mélangeant l'INDICE i et l'EFFECTIF n_i.
#  La formule correcte (Mack 1994) utilise n_i partout. VÉRIFIÉ : la version
#  corrigée reproduit EXACTEMENT le tableau publié par le guide (Figure 52,
#  p81) — n=14 → E(Z)=5,534 et V(Z)=1,350 ; n=12 → 4,646 et 1,168 ; n=11 →
#  4,146 et 0,918 ; n=10 → 3,770 et 0,986. La lecture littérale ne le
#  reproduirait pas. Ces valeurs servent d'oracle aux tests.
#
#  Le guide désigne d'ailleurs le même indice de trois façons contradictoires
#  (« par période de développement i » dans le texte, « Année de survenance »
#  dans l'en-tête de la Figure 52, « par période d'origine » dans sa légende).
#  Les formules, elles, sont sans ambiguïté celles du test d'effet calendaire de
#  Mack : le regroupement se fait PAR DIAGONALE.
#
#  Références
#  ----------
#  · Institut des Actuaires (2023) — Guide de provisionnement des sinistres en
#    assurance non-vie, §3.b p25-26 et annexe 9.d p80-83.
#  · Mack, T. (1994) — "Measuring the Variability of Chain Ladder Reserve
#    Estimates", CAS Forum. Test des signes par année calendaire.
#  · Mack, T. (1993) — ASTIN Bulletin 23(2), pp. 213-225.
# =============================================================================

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from math import comb, sqrt
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger('actuaria.a7')

try:
    from scipy.stats import chi2 as _loi_chi2, spearmanr as _spearmanr, t as _loi_t
    SCIPY_OK = True
except ImportError:                                    # pragma: no cover
    SCIPY_OK = False


# =============================================================================
#  CONVENTION DE STATUT — commune aux quatre hypothèses
# =============================================================================

VALIDEE      = 'VALIDÉE'
A_JUSTIFIER  = 'À JUSTIFIER'
NON_VALIDEE  = 'NON VALIDÉE'
NON_TESTABLE = 'NON TESTABLE'      # données insuffisantes — jamais un jugement

#: Provenance d'un critère — pour qu'un seuil de jugement ne soit jamais lu
#: comme une exigence réglementaire.
SOURCE_GUIDE   = 'guide IA 2023'
SOURCE_JUGEMENT = 'jugement ActuarIA (le guide ne fixe aucun seuil)'

# ── Seuils CLM-H1 — le premier vient du guide, le second est notre jugement ──
H1_SEUIL_REJET      = 1.96    # guide, annexe 9.d p82 : niveau de confiance 95 %
H1_SEUIL_VIGILANCE  = 1.645   # JUGEMENT : niveau 90 %, borne de la zone grise.
                              # Le guide ne prévoit que deux issues (rejet ou
                              # non) ; la convention à trois états en demande une
                              # troisième, que nous plaçons au seuil usuel de 10 %.

# ── Seuils CLM-H2 — JUGEMENT INTÉGRAL, le guide n'en donne aucun ─────────────
#
# ⚠️ LE VERDICT REPOSE SUR L'ORDONNÉE À L'ORIGINE, PAS SUR LE R².
# Le R² est CONSERVÉ et publié parce que le guide l'affiche (0,9817 sur son
# exemple, p83), mais il NE PEUT PAS servir de critère : il mesure l'étendue des
# volumes du portefeuille, pas la validité du modèle proportionnel. Vérifié par
# simulation — même modèle exact `y = 3,5·x` à bruit multiplicatif 5 %, seule
# l'étendue de x changeant :
#       volumes homogènes  (×1,04)  → R² = 0,178
#       modérément variés  (×1,43)  → R² = 0,954
#       en croissance      (×4,50)  → R² = 0,999      ← le cas du guide (25 ans)
# Le test de l'ordonnée, lui, reste correct dans les trois cas. Prendre le R²
# comme critère reviendrait à sanctionner les portefeuilles STABLES, c'est-à-dire
# exactement ceux sur lesquels Chain Ladder est le mieux fondé.
H2_P_ORDONNEE      = 0.05  # ordonnée significative à 5 % → la droite ne passe
                           # pas par l'origine, donc pas de facteur multiplicatif
H2_P_ORDONNEE_FORT = 0.01
H2_CV_VOLUMES_MIN  = 0.05  # en deçà, les volumes sont trop homogènes pour que le
                           # test de l'ordonnée ait du levier → NON TESTABLE,
                           # plutôt qu'un « validé » sans puissance

# ── Seuils CLM-H3 — JUGEMENT INTÉGRAL ────────────────────────────────────────
H3_P_TENDANCE      = 0.05
H3_P_TENDANCE_FORT = 0.01

# ── Seuils CLM-H4 — JUGEMENT INTÉGRAL (hypothèse hors guide) ────────────────
H4_DELTA_AIC_INDISCERNABLE = 2.0   # convention Burnham & Anderson (2002) :
                                   # ΔAIC < 2 ⇒ modèles non départageables
H4_ECART_RESERVE_MAJEUR    = 0.10  # 10 % d'écart de réserve entre courbes
                                   # indiscernables = divergence matérielle

#: Cibles de `critique_pour`, nommées comme dans les autres familles. `MACK`
#: n'est PAS une méthode du Best Estimate — `_CLES_N3` n'en contient que trois.
#: Une hypothèse qui la vise ne peut donc rien retirer par le circuit du BE :
#: il lui faut un PORTEUR propre, exactement comme `PERCENTILES_BOOT` a le
#: sien. C'est `percentiles_mack_publiables`, plus bas.
CHAIN_LADDER    = 'chain_ladder'
MACK            = 'mack'
#: ⚠️ CIBLE DISTINCTE DE `MACK`, ET LA DISTINCTION EST ACTUARIELLE, PAS
#: COSMÉTIQUE. `MACK` désigne le MODÈLE ; `PERCENTILES_MACK` désigne sa MESURE
#: D'INCERTITUDE. Une hétéroscédasticité ne biaise PAS le point estimate — celui
#: de Mack vaut Chain Ladder et n'est pas concerné — elle invalide l'ERREUR DE
#: PRÉDICTION. C'est donc σ_Mack et les percentiles qui en dérivent qui tombent,
#: et eux seuls. Exactement le parallèle de `PERCENTILES_BOOT`.
#:
#: Sans cette distinction, le porteur se déclencherait aussi sur CLM-H2, qui
#: vise `mack` parce qu'elle invalide le MODÈLE : mesuré, deux des cinq
#: scénarios de référence perdraient leurs percentiles Mack. Or CLM-H2 est déjà
#: traitée là où elle doit l'être — PAR ANNÉE, via `couverture_motif` et le
#: filet — et son verdict global agrège des colonnes dont la plupart valident.
PERCENTILES_MACK = 'percentiles_mack'

#: Nombre minimum d'observations pour qu'une régression à 2 paramètres ait un
#: degré de liberté résiduel exploitable.
MIN_OBS_REGRESSION = 4
#: ⚠️ PLUS EXIGEANT QUE POUR LA RÉGRESSION, ET CE N'EST PAS UNE PRÉCAUTION
#: DÉCORATIVE. Le test de l'ordonnée repose sur une loi de Student EXACTE sous
#: erreurs normales : à 4 points il lui reste 2 degrés de liberté, c'est peu
#: mais c'est juste. La corrélation de rang, elle, n'a pas de loi exacte
#: tabulée ici : `scipy` en donne une approximation asymptotique. À 4 points il
#: n'existe que 4! = 24 permutations, donc 24 valeurs possibles de ρ : aucune
#: approximation continue ne peut y être valide.
#:
#: MESURÉ, sur triangles conformes au modèle de Mack (300 répétitions), fausse
#: alarme de CLM-H3 APRÈS correction de multiplicité :
#:       plancher à 4 → 6 colonnes testées → 16,0 %
#:       plancher à 5 → 5 colonnes testées →  6,0 %
#:       plancher à 6 → 4 colonnes testées →  5,7 %
#: Les colonnes de 4 points apportaient donc 10 points de fausse alarme à elles
#: seules, et le passage de 5 à 6 n'apporte plus rien : 5 est le point d'arrêt.
MIN_OBS_CORRELATION = 5


@dataclass(frozen=True)
class ResultatHypothese:
    """Verdict d'une hypothèse — lisible par un actuaire, pas seulement par un
    programme.

    `critique_pour` est DESCRIPTIF et n'est branché sur rien dans ce lot : il
    documente ce que la théorie invalide si l'hypothèse tombe, pour que la
    gouvernance future puisse le lire sans avoir à le redécouvrir.
    """
    code:           str                  # 'CLM-H1' … 'CLM-H4'
    libelle:        str
    statut:         str                  # VALIDÉE | À JUSTIFIER | NON VALIDÉE | NON TESTABLE
    valeur:         Optional[float]      # la grandeur testée (statistique, R², …)
    critere:        str                  # le seuil appliqué, en clair
    source_critere: str                  # guide ou jugement — jamais ambigu
    message:        str                  # langue de l'actuaire
    critique_pour:  Tuple[str, ...] = ()  # ('chain_ladder', 'mack') — descriptif
    detail:         Tuple[Dict[str, Any], ...] = ()   # par diagonale / colonne
    extras:         Dict[str, Any] = field(default_factory=dict)

    def synthese(self) -> Dict[str, Any]:
        """Vue json-sérialisable — livrables, audit, rapport."""
        return {
            'code': self.code, 'libelle': self.libelle, 'statut': self.statut,
            'valeur': (None if self.valeur is None else float(self.valeur)),
            'critere': self.critere, 'source_critere': self.source_critere,
            'message': self.message,
            'critique_pour': list(self.critique_pour),
            'detail': [dict(d) for d in self.detail],
            'extras': dict(self.extras),
        }


# =============================================================================
#  SOURCE UNIQUE — reconstruction des facteurs individuels
# =============================================================================

def facteurs_individuels(
    C: np.ndarray,
) -> List[List[Tuple[int, float, float]]]:
    """Facteurs individuels par colonne, AVEC leur position et leur volume.

    Renvoie `sortie[j] = [(i, f_ij, C[i,j]), …]` avec `f_ij = C[i,j+1]/C[i,j]`.

    UNE SEULE reconstruction pour tous les usages : la position `i` permet de
    regrouper par diagonale (CLM-H1), le volume `C[i,j]` sert de pondération
    (variance, résidus de Pearson), et `C[i,j+1]` se retrouve par `f_ij × C[i,j]`
    sans avoir à le transporter.

    Cette fonction remplace TROIS boucles identiques de `n2_hypotheses.py`
    (H1, H2, H4), qui rebâtissaient chacune les mêmes facteurs avec les mêmes
    gardes. Une quatrième copie subsiste dans `chain_ladder.calculer_facteurs` :
    elle appartient au chemin de calcul du BE, donc hors du périmètre de ce lot.

    Zone connue : `i + j + 1 < n`. Les cellules nulles ou négatives sont
    écartées du RATIO (un facteur exigerait une division par zéro ou changerait
    de signe) — le triangle lui-même n'est jamais transformé.
    """
    n, m = C.shape
    sortie: List[List[Tuple[int, float, float]]] = []
    for j in range(m - 1):
        colonne: List[Tuple[int, float, float]] = []
        for i in range(n):
            if i + j + 1 >= n:
                break
            c_ij, c_ij1 = float(C[i, j]), float(C[i, j + 1])
            if c_ij > 0 and c_ij1 > 0 and np.isfinite(c_ij) and np.isfinite(c_ij1):
                colonne.append((i, c_ij1 / c_ij, c_ij))
        sortie.append(colonne)
    return sortie


def _facteur_agrege(colonne: Sequence[Tuple[int, float, float]]) -> float:
    """f̂_j volume-weighted (Mack 1993) = Σ C[i,j+1] / Σ C[i,j]."""
    if not colonne:
        return 1.0
    volumes = np.array([c for _, _, c in colonne])
    vals    = np.array([f for _, f, _ in colonne])
    return float(np.average(vals, weights=volumes))


def _combiner_p_valeurs(p_valeurs: Sequence[float]) -> Optional[float]:
    """Combinaison de Fisher — `X² = −2 Σ ln(p)`, loi du χ² à 2k degrés.

    POURQUOI. Chaque colonne n'offre que `n−j−1` observations : prise isolément,
    elle n'a quasiment aucune puissance. Un verdict global bâti sur des tests
    tous sous-puissants serait sous-puissant à son tour, et rendrait « validé »
    par défaut d'information. Fisher agrège les colonnes — approximativement
    indépendantes sous les hypothèses de Mack — et rend au verdict d'ensemble la
    puissance que chaque colonne n'a pas.
    """
    p = [min(max(float(x), 1e-12), 1.0) for x in p_valeurs if x is not None]
    if not p or not SCIPY_OK:
        return None
    stat = -2.0 * float(np.sum(np.log(p)))
    return float(_loi_chi2.sf(stat, 2 * len(p)))


# =============================================================================
#  CLM-H1 — INDÉPENDANCE DES ANNÉES DE SURVENANCE (EFFET CALENDAIRE)
# =============================================================================

def _esperance_variance_Z(n_d: int) -> Tuple[float, float]:
    """E(Z) et Var(Z) du test des signes, formules de Mack 1994.

    VERSION CORRIGÉE des coquilles du guide (cf. en-tête) :

        c   = C(n−1, ⌊(n−1)/2⌋) × n / 2^n
        E(Z) = n/2 − c
        Var(Z) = n(n−1)/4 − c(n−1) + E(Z) − E(Z)²

    Reproduit le tableau publié du guide (Figure 52) — c'est l'oracle du test.
    """
    c = comb(n_d - 1, (n_d - 1) // 2) * n_d / (2 ** n_d)
    esperance = n_d / 2.0 - c
    variance  = (n_d * (n_d - 1) / 4.0 - c * (n_d - 1)
                 + esperance - esperance ** 2)
    return esperance, max(variance, 0.0)


def _statistique_des_signes(
    C: np.ndarray,
) -> Tuple[List[Dict[str, Any]], float, float, float]:
    """Signes par rapport à la médiane de colonne, regroupés PAR DIAGONALE.

    Rend le détail par diagonale et les trois sommes ΣZ, ΣE(Z), ΣVar(Z) dont le
    test tire sa statistique.
    """
    signes: Dict[int, List[int]] = {}        # diagonale → [+1, −1, …]
    for j, colonne in enumerate(facteurs_individuels(C)):
        if len(colonne) < 2:
            continue                          # pas de médiane exploitable
        mediane = float(np.median([f for _, f, _ in colonne]))
        for i, f, _ in colonne:
            if f == mediane:
                continue                      # égalité : écartée (guide, p81)
            # Le passage de C[i,j] à C[i,j+1] a lieu en année calendaire
            # i + j + 1 : c'est la diagonale qui le porte.
            signes.setdefault(i + j + 1, []).append(1 if f > mediane else -1)

    detail: List[Dict[str, Any]] = []
    somme_Z = somme_E = somme_V = 0.0
    for d in sorted(signes):
        plus  = sum(1 for s in signes[d] if s > 0)
        moins = sum(1 for s in signes[d] if s < 0)
        n_d   = plus + moins
        if n_d <= 1:
            # Le guide l'impose : « Il faudra retirer tous les Z_i où n_i ≤ 1 car
            # dans ce cas l'espérance est nécessairement égale à notre valeur
            # observée » (p81).
            continue
        esp, var = _esperance_variance_Z(n_d)
        somme_Z += min(plus, moins); somme_E += esp; somme_V += var
        detail.append({'diagonale': d, 'n_plus': plus, 'n_moins': moins,
                       'n': n_d, 'Z': min(plus, moins),
                       'E_Z': round(esp, 4), 'Var_Z': round(var, 4)})
    return detail, somme_Z, somme_E, somme_V


def clm_h1_effet_calendaire(C: np.ndarray) -> ResultatHypothese:
    """CLM-H1 — un effet propre à une année CALENDAIRE contamine-t-il le triangle ?

    Méthode de l'annexe 9.d : dans chaque colonne de développement, chaque
    facteur est noté « + » s'il dépasse la médiane de sa colonne, « − » sinon
    (les égalités sont écartées). Sous l'hypothèse d'indépendance, les « + » et
    les « − » doivent se répartir au hasard sur les diagonales. On regroupe donc
    PAR DIAGONALE, et l'on teste `Z_d = min(n_d+, n_d−)`.

    Une diagonale = une année calendaire : un changement de politique de
    règlement, une inflation, un rattrapage de dossiers se lisent là, et nulle
    part ailleurs.

    Le guide REJETTE cette hypothèse sur son propre exemple (t = −2,31) et
    poursuit néanmoins : l'échec ne bloque rien, il réoriente le choix des
    coefficients (cf. Remarque p82). D'où `critique_pour = ()`.

    ⚠️ CE QUE CE TEST NE PEUT PAS VOIR — une inflation calendaire CONSTANTE.
    Vérifié par construction : si chaque incrément est multiplié par (1+g)^(i+j),
    les cumulés valent `base_i × (1+g)^i × A_j`, donc tous les facteurs d'une
    même colonne deviennent IDENTIQUES — le triangle est parfaitement régulier
    et aucun test de signes ne peut rien y lire. L'inflation constante est
    absorbée par le niveau de l'année de survenance et par la cadence : c'est un
    mur d'identifiabilité, pas une faiblesse de l'implémentation (même constat
    que pour le GLM APC du module n3). CE TEST DÉTECTE LES RUPTURES — chocs,
    changements de régime, rattrapages —, pas les tendances régulières. Un
    statut VALIDÉE ne certifie donc PAS l'absence d'inflation.
    """
    detail, somme_Z, somme_E, somme_V = _statistique_des_signes(C)

    if not detail or somme_V <= 0:
        return ResultatHypothese(
            code='CLM-H1', libelle="Indépendance des années de survenance",
            statut=NON_TESTABLE, valeur=None,
            critere=f"|t| vs {H1_SEUIL_REJET}", source_critere=SOURCE_GUIDE,
            message=("Triangle trop court pour le test des signes : aucune "
                     "diagonale ne porte au moins deux facteurs comparables."),
            detail=tuple(detail))

    t_stat = (somme_Z - somme_E) / sqrt(somme_V)
    borne_basse = somme_E - 2.0 * sqrt(somme_V)
    borne_haute = somme_E + 2.0 * sqrt(somme_V)

    if abs(t_stat) > H1_SEUIL_REJET:
        statut = NON_VALIDEE
        message = (
            f"Un effet d'année calendaire est détecté (statistique {t_stat:+.2f}, "
            f"hors de l'intervalle [−1,96 ; 1,96] au seuil de 95 %). Certaines "
            f"années de règlement se comportent différemment des autres — "
            f"inflation, changement de politique de gestion ou rattrapage de "
            f"dossiers. Chain Ladder reste applicable, mais la période servant à "
            f"calculer les coefficients mérite d'être resserrée sur les années "
            f"récentes, et ce choix documenté.")
    elif abs(t_stat) > H1_SEUIL_VIGILANCE:
        statut = A_JUSTIFIER
        message = (
            f"Un effet d'année calendaire est possible sans être établi "
            f"(statistique {t_stat:+.2f} : au-delà du seuil de 90 %, en deçà de "
            f"celui de 95 %). À rapprocher de ce que l'on sait des exercices "
            f"concernés avant de retenir la période de calcul.")
    else:
        statut = VALIDEE
        message = (
            f"Aucun effet d'année calendaire décelé (statistique {t_stat:+.2f}, "
            f"dans l'intervalle [−1,96 ; 1,96]). Les années de règlement se "
            f"comportent de façon homogène.")

    return ResultatHypothese(
        code='CLM-H1', libelle="Indépendance des années de survenance",
        statut=statut, valeur=round(t_stat, 4),
        critere=(f"|t| ≤ {H1_SEUIL_VIGILANCE} validée · "
                 f"≤ {H1_SEUIL_REJET} à justifier · au-delà non validée"),
        source_critere=(f"{SOURCE_GUIDE} pour le seuil {H1_SEUIL_REJET} "
                        f"(annexe 9.d p82) ; seuil intermédiaire "
                        f"{H1_SEUIL_VIGILANCE} = jugement ActuarIA"),
        message=message,
        critique_pour=(),          # le guide rejette et poursuit : jamais bloquant
        detail=tuple(detail),
        extras={'somme_Z': round(somme_Z, 4), 'somme_E': round(somme_E, 4),
                'somme_Var': round(somme_V, 4),
                'intervalle_2sigma': [round(borne_basse, 4), round(borne_haute, 4)],
                'n_diagonales_testees': len(detail)})


# =============================================================================
#  CLM-H2 — EXISTENCE DES FACTEURS DE DÉVELOPPEMENT
# =============================================================================

def _regression_origine(x: np.ndarray, y: np.ndarray) -> Optional[Dict[str, float]]:
    """Régression y = a + b·x — rend R² et la significativité de `a`.

    L'hypothèse `E(C[i,j+1] | C[i,j]) = λ_j · C[i,j]` impose une droite qui
    passe PAR L'ORIGINE. On ajuste donc avec ordonnée, puis on teste si celle-ci
    est significativement différente de zéro : si elle l'est, la relation n'est
    pas multiplicative et le facteur de développement n'existe pas.
    """
    n = len(x)
    if n < MIN_OBS_REGRESSION or not SCIPY_OK:
        return None
    x_moy, y_moy = float(np.mean(x)), float(np.mean(y))
    sxx = float(np.sum((x - x_moy) ** 2))
    if sxx <= 0:
        return None
    pente    = float(np.sum((x - x_moy) * (y - y_moy)) / sxx)
    ordonnee = y_moy - pente * x_moy
    ajuste   = ordonnee + pente * x
    sce      = float(np.sum((y - ajuste) ** 2))          # somme des carrés résiduels
    sct      = float(np.sum((y - y_moy) ** 2))           # somme des carrés totale
    r2       = 1.0 - sce / sct if sct > 0 else 1.0
    ddl      = n - 2
    if ddl <= 0 or sce <= 0:
        # Ajustement parfait : l'ordonnée ne peut pas être déclarée significative.
        return {'r2': r2, 'ordonnee': ordonnee, 'pente': pente,
                'p_ordonnee': 1.0, 'n': n}
    s2       = sce / ddl
    se_ord   = sqrt(s2 * (1.0 / n + x_moy ** 2 / sxx))
    if se_ord <= 0:
        return {'r2': r2, 'ordonnee': ordonnee, 'pente': pente,
                'p_ordonnee': 1.0, 'n': n}
    t_ord    = ordonnee / se_ord
    p_ord    = 2.0 * float(_loi_t.sf(abs(t_ord), ddl))
    return {'r2': r2, 'ordonnee': ordonnee, 'pente': pente,
            'p_ordonnee': p_ord, 'n': n}


def clm_h2_existence_facteurs(C: np.ndarray) -> ResultatHypothese:
    """CLM-H2 — les montants d'une période à la suivante sont-ils proportionnels ?

    Pour chaque colonne, on porte `C[i,j+1]` en fonction de `C[i,j]` et l'on
    vérifie que les points s'alignent SUR UNE DROITE PASSANT PAR L'ORIGINE —
    c'est exactement ce que le guide propose (§9.d.ii, p83, avec un R² de 0,9817
    sur son exemple).

    LE VERDICT PORTE SUR L'ORDONNÉE À L'ORIGINE : si elle est significativement
    différente de zéro, la relation n'est pas multiplicative et le facteur de
    développement n'existe pas — ni pour Chain Ladder, ni pour Mack, d'où
    `critique_pour` = les deux. Le R² est calculé et publié (le guide l'affiche)
    mais NE SERT PAS de critère : il dépend de l'étendue des volumes, pas de la
    validité du modèle — cf. la démonstration en tête des constantes H2_*.

    ⚠️ AUCUN SEUIL N'EST DONNÉ PAR LE GUIDE. Ceux appliqués ici sont notre
    jugement, cf. les constantes H2_* et leur commentaire.
    """
    colonnes = facteurs_individuels(C)
    detail: List[Dict[str, Any]] = []
    for j, colonne in enumerate(colonnes):
        if len(colonne) < MIN_OBS_REGRESSION:
            detail.append({'colonne': j, 'n': len(colonne),
                           'statut': NON_TESTABLE})
            continue
        x = np.array([c for _, _, c in colonne])
        y = np.array([f * c for _, f, c in colonne])      # C[i,j+1]
        cv_x = float(np.std(x) / np.mean(x)) if np.mean(x) > 0 else 0.0
        reg = _regression_origine(x, y)
        if reg is None:
            detail.append({'colonne': j, 'n': len(colonne),
                           'statut': NON_TESTABLE})
            continue
        if cv_x < H2_CV_VOLUMES_MIN:
            # Volumes trop homogènes : la régression n'a pas de levier pour
            # distinguer une droite par l'origine d'une droite décalée. On le
            # dit, plutôt que de rendre un « validé » sans puissance.
            detail.append({'colonne': j, 'n': reg['n'], 'statut': NON_TESTABLE,
                           'r2': round(reg['r2'], 4), 'cv_volumes': round(cv_x, 4),
                           'motif': 'volumes trop homogènes'})
            continue
        # Le STATUT n'est pas décidé ici : il l'est dans `_agreger_par_colonne`,
        # après correction de multiplicité sur l'ensemble des colonnes.
        detail.append({'colonne': j, 'n': reg['n'],
                       'r2': round(reg['r2'], 4),          # descriptif, cf. H2_*
                       'cv_volumes': round(cv_x, 4),
                       'ordonnee': round(reg['ordonnee'], 2),
                       'p_ordonnee': round(reg['p_ordonnee'], 4)})

    return _agreger_par_colonne(
        detail,
        cle_p='p_ordonnee', seuil_fort=H2_P_ORDONNEE_FORT,
        seuil_souple=H2_P_ORDONNEE,
        code='CLM-H2', libelle="Existence des facteurs de développement",
        critere=(f"par colonne : ordonnée à l'origine non significative "
                 f"(p ≥ {H2_P_ORDONNEE}) → validée ; p < {H2_P_ORDONNEE_FORT} → "
                 f"non validée. Seuils corrigés de la multiplicité par "
                 f"Holm-Bonferroni sur l'ensemble des colonnes testées. Le R² "
                 f"est publié mais n'entre pas dans le verdict"),
        source_critere=SOURCE_JUGEMENT,
        critique_pour=('chain_ladder', 'mack'),
        libelle_ok=("Les montants cumulés progressent proportionnellement d'une "
                    "période à la suivante : un coefficient de passage a bien un "
                    "sens sur ce triangle."),
        libelle_ko=("Sur {n_ko} période(s) de développement, les montants ne "
                    "progressent pas proportionnellement — la relation ne passe "
                    "pas par l'origine ou n'est pas linéaire. Un coefficient de "
                    "passage unique y est mal fondé, pour Chain Ladder comme pour "
                    "Mack."),
        libelle_mitige=("Sur {n_ko} période(s), la proportionnalité est imparfaite "
                        "sans être démentie. À examiner colonne par colonne avant "
                        "de retenir les coefficients."))


# =============================================================================
#  CLM-H3 — STRUCTURE DE VARIANCE
# =============================================================================

def _durcir_avec_le_test_combine(
    resultat: ResultatHypothese,
    p_global: Optional[float],
) -> ResultatHypothese:
    """Confronte le verdict par colonne au test combiné.

    Le combiné ne peut que DURCIR : il apporte de la puissance là où chaque
    colonne en manque, il n'en retire jamais à un signal déjà vu. Un verdict
    sévère obtenu colonne par colonne n'est donc jamais adouci.
    """
    if p_global is None or resultat.statut == NON_TESTABLE:
        return resultat
    ordre = {NON_VALIDEE: 3, A_JUSTIFIER: 2, VALIDEE: 1}
    if p_global < H3_P_TENDANCE_FORT:
        statut_global = NON_VALIDEE
    elif p_global < H3_P_TENDANCE:
        statut_global = A_JUSTIFIER
    else:
        statut_global = VALIDEE
    extras = {**resultat.extras, 'p_combine_fisher': round(p_global, 5)}
    if ordre[statut_global] <= ordre.get(resultat.statut, 1):
        return ResultatHypothese(**{**resultat.__dict__, 'extras': extras})
    return ResultatHypothese(**{
        **resultat.__dict__, 'statut': statut_global,
        'extras': {**extras, 'statut_par_colonne_seul': resultat.statut},
        'message': (
            f"Prise colonne par colonne la dispersion paraît acceptable, mais "
            f"l'ensemble du triangle raconte autre chose : en agrégeant les "
            f"périodes (test combiné, p = {p_global:.4f}), la dispersion ne suit "
            f"pas le volume comme Mack le suppose. Chaque période prise seule "
            f"compte trop peu d'observations pour le montrer. L'écart-type et "
            f"les percentiles publiés sont à interpréter avec prudence ; la "
            f"réserve centrale de Chain Ladder, elle, n'est pas concernée.")})


def clm_h3_structure_variance(C: np.ndarray) -> ResultatHypothese:
    """CLM-H3 — la dispersion croît-elle bien comme le volume ?

    Mack pose `Var(C[i,j+1] | C[i,j]) = σ²_j · C[i,j]` : la variance est
    proportionnelle au montant déjà réglé, avec un σ²_j PROPRE À CHAQUE COLONNE
    — Mack n'exige nullement que σ² soit le même d'une colonne à l'autre.

    Le guide (§9.d.iii, p83) demande de porter les résidus
    `(C[i,j+1] − λ̂_j·C[i,j]) / √C[i,j]` en fonction de `C[i,j]` et de vérifier
    qu'ils « ne montrent pas de tendance spécifique ». On formalise ce contrôle
    visuel par un test de corrélation de rang entre |résidu| et C[i,j] : si la
    dispersion croît (ou décroît) avec le volume, la mise à l'échelle en √C
    n'est pas la bonne.

    CRITIQUE POUR MACK SEUL. Le point estimate de Chain Ladder ne dépend
    d'aucune hypothèse de variance ; σ, la MSEP et les percentiles publiés en
    dépendent entièrement.

    ⚠️ AUCUN SEUIL N'EST DONNÉ PAR LE GUIDE (il ne propose même pas de test
    formel). Les seuils H3_* sont notre jugement.
    """
    colonnes = facteurs_individuels(C)
    detail: List[Dict[str, Any]] = []
    for j, colonne in enumerate(colonnes):
        if len(colonne) < MIN_OBS_CORRELATION or not SCIPY_OK:
            detail.append({'colonne': j, 'n': len(colonne),
                           'statut': NON_TESTABLE})
            continue
        f_chap = _facteur_agrege(colonne)
        vol = np.array([c for _, _, c in colonne])
        # Résidu de Pearson : (C[i,j+1] − f̂_j·C[i,j]) / √C[i,j]
        res = np.array([(f * c - f_chap * c) / sqrt(c) for _, f, c in colonne])
        if np.allclose(res, 0.0):
            # Ajustement parfait : aucune dispersion à structurer. La colonne
            # porte bien une p-valeur — « aucune tendance décelable » est un
            # résultat de test — elle entre donc dans la famille comme les
            # autres, et Holm ne la rejettera jamais.
            detail.append({'colonne': j, 'n': len(colonne),
                           'rho': 0.0, 'p': 1.0})
            continue
        rho, p = _spearmanr(np.abs(res), vol)
        if not np.isfinite(rho):
            detail.append({'colonne': j, 'n': len(colonne),
                           'statut': NON_TESTABLE})
            continue
        # Le STATUT n'est pas décidé ici : cf. `_agreger_par_colonne`.
        detail.append({'colonne': j, 'n': len(colonne),
                       'rho': round(float(rho), 4), 'p': round(float(p), 4)})

    # ── Verdict d'ensemble renforcé (Fisher) ────────────────────────────────
    p_global = _combiner_p_valeurs([d['p'] for d in detail
                                    if d.get('p') is not None])
    resultat = _agreger_par_colonne(
        detail,
        cle_p='p', seuil_fort=H3_P_TENDANCE_FORT,
        seuil_souple=H3_P_TENDANCE,
        code='CLM-H3', libelle="Structure de variance",
        critere=(f"par colonne : corrélation de rang |résidu| vs volume, "
                 f"p ≥ {H3_P_TENDANCE} → validée ; p < {H3_P_TENDANCE_FORT} → "
                 f"non validée. Seuils corrigés de la multiplicité par "
                 f"Holm-Bonferroni sur l'ensemble des colonnes testées"),
        source_critere=SOURCE_JUGEMENT,
        critique_pour=(PERCENTILES_MACK,),
        libelle_ok=("La dispersion des règlements croît bien comme le volume : "
                    "la mesure d'incertitude de Mack repose sur une base saine."),
        libelle_ko=("Sur {n_ko} période(s), la dispersion ne suit pas le volume "
                    "comme Mack le suppose. L'écart-type et les percentiles "
                    "publiés sont à interpréter avec prudence ; la réserve "
                    "centrale de Chain Ladder, elle, n'est pas concernée."),
        libelle_mitige=("Sur {n_ko} période(s), la dispersion s'écarte du profil "
                        "attendu sans le contredire nettement. Sans effet sur la "
                        "réserve centrale ; à garder à l'esprit pour les "
                        "percentiles."))

    return _durcir_avec_le_test_combine(resultat, p_global)


# =============================================================================
#  CLM-H4 — INCERTITUDE DE LA QUEUE DE DÉVELOPPEMENT  (Mack uniquement)
# =============================================================================

def _sensibilite_aux_queues(
    C:            np.ndarray,
    facteurs:     np.ndarray,
    comparaison:  Dict[str, Any],
    annee_base:   int,
    projeter,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float]:
    """Réserve obtenue avec CHAQUE courbe de queue non départageable.

    Ne retient que les courbes dont l'AIC est à moins de `H4_DELTA_AIC_
    INDISCERNABLE` de la meilleure : au-delà, les données tranchent, et une
    courbe écartée n'est pas une incertitude. Rend (tous les candidats, la
    fourchette des courbes retenues, l'écart relatif de réserve).
    """
    candidats: List[Dict[str, Any]] = []
    aic_retenu: Optional[float] = None
    for nom, d in comparaison.items():
        if not isinstance(d, dict) or d.get('echec'):
            continue
        tail_c, aic_c = d.get('tail'), d.get('aic')
        if tail_c is None or aic_c is None:
            continue
        candidats.append({'methode': nom, 'tail': float(tail_c),
                          'aic': float(aic_c), 'retenu': bool(d.get('retenu'))})
        if d.get('retenu'):
            aic_retenu = float(aic_c)
    if aic_retenu is None and candidats:
        aic_retenu = min(c['aic'] for c in candidats)

    sensibilite: List[Dict[str, Any]] = []
    for c in candidats:
        if aic_retenu is None or c['aic'] - aic_retenu >= H4_DELTA_AIC_INDISCERNABLE:
            continue
        proj = projeter(C, facteurs, tail_factor=c['tail'], annee_base=annee_base)
        sensibilite.append({'methode': c['methode'], 'tail': round(c['tail'], 6),
                            'delta_aic': round(c['aic'] - aic_retenu, 3),
                            'reserve': round(float(proj['reserve_brute']), 0)})

    reserves = [s['reserve'] for s in sensibilite if s['reserve'] > 0]
    ecart = ((max(reserves) - min(reserves)) / max(reserves)
             if len(reserves) >= 2 else 0.0)
    return candidats, sensibilite, ecart


def clm_h4_incertitude_queue(
    C:            np.ndarray,
    tail_info:    Optional[Dict[str, Any]] = None,
    facteurs:     Optional[np.ndarray] = None,
    annee_base:   int = 1,
) -> ResultatHypothese:
    """CLM-H4 — la volatilité publiée couvre-t-elle l'incertitude de la queue ?

    ⚠️ CETTE HYPOTHÈSE N'EST PAS DANS LE GUIDE. Elle répond à une LIMITE
    STRUCTURELLE de Mack 1993 : la MSEP traite le facteur de queue comme
    parfaitement connu. Conséquence mesurée sur RAA — plus la queue est longue,
    plus le coefficient de variation AFFICHÉ baisse (51,6 % à tail=1,00 ;
    45,7 % à 1,05 ; 35,5 % à 1,20), ce qui est l'inverse du bon sens.

    Elle diffère des trois autres par nature : H1/H2/H3 se testent SUR LA
    DONNÉE ; H4 existe dès qu'une queue est appliquée, même sur un triangle
    parfait.

    MESURE RETENUE — `calculer_tail_factor_multi` ajuste DÉJÀ trois courbes
    (log-linéaire, inverse power, exponential decay) et n'en retient qu'une par
    AIC. Les autres sont jetées : ce sont pourtant la mesure gratuite de
    l'incertitude de modèle sur la queue. Deux courbes dont les AIC diffèrent de
    moins de 2 ne sont pas départageables (Burnham & Anderson 2002) ; si elles
    donnent des réserves très différentes, l'incertitude est réelle et mesurée.

    POURQUOI PAS UNE COLONNE DE QUEUE À σ² EXTRAPOLÉ — mesuré sur GenIns :
    cette correction n'ajouterait que 0,28 % de variance, quand deux courbes
    indiscernables (ΔAIC = 0,44) donnent des réserves écartées de 78 %. Elle
    produirait un MSEP d'apparence rigoureuse mais faux de deux ordres de
    grandeur, et autoriserait un statut VALIDÉE trompeur. Écartée sciemment.

    NON CRITIQUE : Mack continue de produire un σ. Refuser toute volatilité
    serait pire qu'une volatilité assortie d'un avertissement. Mais un statut
    NON VALIDÉE produit `avertissement_percentiles`, destiné à être accroché
    AUX PERCENTILES EUX-MÊMES.
    """
    from .n3.chain_ladder import calculer_facteurs, calculer_tail_factor_multi
    from direction_non_vie.services.nv_triangle_projection import projeter_ultimates

    if facteurs is None:
        facteurs, _ = calculer_facteurs(C, 'standard')
    if tail_info is None:
        tail_info = calculer_tail_factor_multi(facteurs)

    tail_retenu = float(tail_info.get('tail_factor', 1.0))
    comparaison = tail_info.get('comparaison_methodes', {}) or {}

    base = {'code': 'CLM-H4',
            'libelle': "Incertitude de la queue de développement",
            'critique_pour': (),
            'source_critere': SOURCE_JUGEMENT}

    # ── Cas 1 : aucune queue appliquée ──────────────────────────────────────
    if abs(tail_retenu - 1.0) < 1e-9:
        return ResultatHypothese(
            **base, statut=VALIDEE, valeur=1.0,
            critere="aucune queue appliquée",
            message=("Aucun facteur de queue n'est appliqué : la mesure "
                     "d'incertitude de Mack porte sur l'intégralité du "
                     "développement retenu, il n'y a rien à justifier."),
            extras={'tail_retenu': 1.0, 'candidats': {}})

    candidats, sensibilite, ecart_rel = _sensibilite_aux_queues(
        C, facteurs, comparaison, annee_base, projeter_ultimates)

    extras = {'tail_retenu': round(tail_retenu, 6),
              'candidats': candidats,
              'sensibilite': sensibilite,
              'ecart_relatif_reserve': round(ecart_rel, 4),
              'n_rivaux_indiscernables': max(0, len(sensibilite) - 1)}

    # ── Statut — une queue appliquée n'est JAMAIS validée sans justification ─
    if ecart_rel > H4_ECART_RESERVE_MAJEUR:
        pire = max(sensibilite, key=lambda s: s['reserve'])
        moindre = min(sensibilite, key=lambda s: s['reserve'])
        extras['avertissement_percentiles'] = (
            "Volatilité MINORÉE : elle n'inclut pas l'incertitude de la queue "
            "de développement.")
        return ResultatHypothese(
            **base, statut=NON_VALIDEE, valeur=round(ecart_rel, 4),
            critere=(f"écart de réserve entre courbes indiscernables "
                     f"(ΔAIC < {H4_DELTA_AIC_INDISCERNABLE}) > "
                     f"{H4_ECART_RESERVE_MAJEUR:.0%}"),
            message=(
                f"La queue de développement pèse {tail_retenu:.3f} sur les "
                f"ultimes, mais elle n'est pas déterminée par les données : "
                f"plusieurs courbes d'extrapolation s'ajustent aussi bien "
                f"l'une que l'autre et donnent des réserves allant de "
                f"{moindre['reserve']:,.0f} € à {pire['reserve']:,.0f} € "
                f"(écart {ecart_rel:.0%}). L'écart-type publié par Mack ne "
                f"couvre PAS cette incertitude : il la traite comme nulle. "
                f"Les percentiles sont donc MINORÉS."),
            detail=tuple(sensibilite), extras=extras)

    return ResultatHypothese(
        **base, statut=A_JUSTIFIER, valeur=round(ecart_rel, 4),
        critere=(f"une queue est appliquée : jamais validée sans justification ; "
                 f"non validée si l'écart de réserve dépasse "
                 f"{H4_ECART_RESERVE_MAJEUR:.0%}"),
        message=(
            f"Une queue de développement de {tail_retenu:.3f} est appliquée. "
            f"Les courbes d'extrapolation envisageables concordent "
            f"(écart de réserve {ecart_rel:.0%}), mais l'écart-type publié par "
            f"Mack traite cette queue comme parfaitement connue : il ignore "
            f"l'incertitude qui lui est propre. Le choix de la queue doit être "
            f"justifié dans la note méthodologique."),
        detail=tuple(sensibilite), extras=extras)


# =============================================================================
#  AGRÉGATION D'UN VERDICT PAR COLONNE  (H2 et H3)
# =============================================================================

def _holm_bonferroni(p_valeurs: Sequence[float], alpha: float) -> set:
    """Indices rejetés au niveau `alpha` SUR L'ENSEMBLE de la famille.

    Procédure descendante de Holm (1979) : on ordonne les p-valeurs et l'on
    rejette tant que `p_(r) ≤ alpha / (k − r + 1)`, en s'arrêtant au premier
    échec. Elle contrôle le risque de première espèce FAMILIAL — la probabilité
    de se tromper NE SERAIT-CE QUE SUR UNE colonne — et elle le fait sous une
    dépendance ARBITRAIRE entre les colonnes. C'est précisément le cas ici :
    les colonnes d'un même triangle partagent leurs années de survenance, elles
    ne sont pas indépendantes.

    Holm est UNIFORMÉMENT plus puissante que Bonferroni (le premier seuil vaut
    `alpha/k` dans les deux cas, les suivants sont plus larges chez Holm) pour
    le même contrôle du risque : il n'y a aucune raison de préférer Bonferroni.
    """
    k = len(p_valeurs)
    if k == 0:
        return set()
    rejetes: set = set()
    for rang, i in enumerate(sorted(range(k), key=lambda i: p_valeurs[i])):
        if p_valeurs[i] > alpha / (k - rang):
            break
        rejetes.add(i)
    return rejetes


def _statuts_corriges(
    detail:       List[Dict[str, Any]],
    cle_p:        str,
    seuil_fort:   float,
    seuil_souple: float,
) -> Tuple[List[Dict[str, Any]], int]:
    """Attribue les statuts de colonne APRÈS correction de multiplicité.

    ⚠️ LA CORRECTION PORTE SUR LES COLONNES, PAS SUR LE SEUL VERDICT GLOBAL, ET
    CE N'EST PAS UN DÉTAIL D'IMPLÉMENTATION. `couvertures_par_annee` lit
    `detail[j]['statut']` colonne par colonne pour dire quelles années de
    survenance sont couvertes. Ne corriger que le verdict d'ensemble ferait
    diverger les deux lectures, et invaliderait la démonstration du lot A2
    (`n4_best_estimate`) : « le motif de l'année la plus récente EST le statut
    global », qui n'est vraie que si les deux appliquent la même règle aux
    mêmes statuts.

    La famille, c'est l'ensemble des colonnes qui portent une p-valeur — donc
    celles sur lesquelles un test a réellement été conduit. Une colonne
    NON TESTABLE n'en fait pas partie : elle n'a pas de p-valeur, et n'a donc
    aucune raison de durcir le seuil des autres.

    ⚠️ LA DÉCISION EMPLOIE LA P-VALEUR PUBLIÉE, arrondie comme elle l'est dans
    `detail`. C'est délibéré : le nombre imprimé dans le rapport et le verdict
    qui l'accompagne ne peuvent jamais se contredire, ce qui est la propriété
    qu'un contrôleur vérifiera. L'écart possible se loge dans une bande de
    5·10⁻⁵ autour du seuil, et il est sans direction privilégiée.
    """
    indices = [i for i, d in enumerate(detail) if d.get(cle_p) is not None]
    if not indices:
        return list(detail), 0
    p_valeurs = [float(detail[i][cle_p]) for i in indices]
    forts   = _holm_bonferroni(p_valeurs, seuil_fort)
    souples = _holm_bonferroni(p_valeurs, seuil_souple)
    sortie = list(detail)
    for rang, i in enumerate(indices):
        sortie[i] = {**detail[i],
                     'statut': (NON_VALIDEE if rang in forts else
                                A_JUSTIFIER if rang in souples else VALIDEE)}
    return sortie, len(p_valeurs)


def _agreger_par_colonne(
    detail:         List[Dict[str, Any]],
    *,
    code:           str,
    libelle:        str,
    critere:        str,
    source_critere: str,
    critique_pour:  Tuple[str, ...],
    libelle_ok:     str,
    libelle_ko:     str,
    libelle_mitige: str,
    cle_p:          str,
    seuil_fort:     float,
    seuil_souple:   float,
) -> ResultatHypothese:
    """Verdict d'ensemble à partir des verdicts par colonne — le plus sévère
    l'emporte, et le message dit COMBIEN de colonnes sont en cause.

    ⚠️ LES STATUTS DE COLONNE SONT DÉCIDÉS ICI, ET NULLE PART AILLEURS. Ils
    l'étaient auparavant chez chaque appelant, en comparant la p-valeur brute
    aux seuils — donc sans jamais tenir compte du fait qu'on pose la question
    à neuf colonnes à la fois. Avec neuf tests indépendants à 5 %, la
    probabilité qu'AU MOINS UN se déclenche sur un triangle parfaitement sain
    vaut `1 − 0,95⁹ = 37,0 %` ; la fausse alarme mesurée de CLM-H3 valait
    35,2 %. La règle « le plus sévère l'emporte » n'était pas un choix de
    prudence : c'était une multiplicité non corrigée.

    Centraliser la décision ici est ce qui rend l'oubli impossible : un
    troisième test par colonne héritera de la correction sans que personne ait
    à y penser.
    """
    detail, n_famille = _statuts_corriges(detail, cle_p, seuil_fort,
                                          seuil_souple)
    testees = [d for d in detail if d.get('statut') != NON_TESTABLE]
    if not testees:
        return ResultatHypothese(
            code=code, libelle=libelle, statut=NON_TESTABLE, valeur=None,
            critere=critere, source_critere=source_critere,
            message=("Triangle trop court : aucune période de développement ne "
                     "porte assez d'observations pour être testée."),
            critique_pour=critique_pour, detail=tuple(detail))

    n_non   = sum(1 for d in testees if d['statut'] == NON_VALIDEE)
    n_just  = sum(1 for d in testees if d['statut'] == A_JUSTIFIER)
    if n_non:
        statut, message = NON_VALIDEE, libelle_ko.format(n_ko=n_non)
    elif n_just:
        statut, message = A_JUSTIFIER, libelle_mitige.format(n_ko=n_just)
    else:
        statut, message = VALIDEE, libelle_ok

    return ResultatHypothese(
        code=code, libelle=libelle, statut=statut,
        valeur=round(n_non + n_just, 0), critere=critere,
        source_critere=source_critere, message=message,
        critique_pour=critique_pour, detail=tuple(detail),
        extras={'n_colonnes_testees': len(testees),
                'n_non_validees': n_non, 'n_a_justifier': n_just,
                'n_non_testables': len(detail) - len(testees),
                'correction_multiplicite': 'Holm-Bonferroni',
                'n_tests_famille': n_famille})


# =============================================================================
#  COUVERTURE PAR ANNÉE DE SURVENANCE
# =============================================================================

_ORDRE_SEVERITE = {NON_TESTABLE: 0, VALIDEE: 1, A_JUSTIFIER: 2, NON_VALIDEE: 3}


def _pire_statut(statuts: Sequence[str]) -> str:
    """Le plus sévère l'emporte. NON TESTABLE = absence d'information, il ne
    dégrade rien mais ne valide rien non plus."""
    connus = [s for s in statuts if s in _ORDRE_SEVERITE]
    if not connus:
        return NON_TESTABLE
    return max(connus, key=lambda s: _ORDRE_SEVERITE[s])


def percentiles_mack_publiables(
    hypotheses: Dict[str, ResultatHypothese],
) -> bool:
    """Les percentiles de Mack sont-ils opposables ?

    NON dès qu'une hypothèse portant `PERCENTILES_MACK` est NON VALIDÉE —
    c'est CLM-H3, la structure de variance. Une hypothèse NON TESTABLE ne retire rien : ne pas
    avoir pu juger n'est pas juger défavorablement. Même convention, mot pour
    mot, que `percentiles_publiables` côté Bootstrap.

    ⚠️ POURQUOI CE PORTEUR EXISTE. Aucune de ces deux cibles n'est dans
    `_CLES_N3` : rejeter
    CLM-H3 ne peut donc PAS retirer une méthode du Best Estimate — Mack n'y
    figure pas, son point estimate VAUT Chain Ladder. Ce qui est en cause, c'est
    son ÉCART-TYPE : si la dispersion ne suit pas le volume comme Mack le
    suppose, σ_Mack ne mesure plus l'erreur de prédiction. Ce sont donc les
    PERCENTILES qui tombent, et eux seuls.

    ⚠️ ET CE PORTEUR N'EST PAS SYMÉTRIQUE DE CELUI DU BOOTSTRAP, malgré la
    ressemblance. Les percentiles Bootstrap sont une colonne COMPARATIVE : les
    retirer retire un point de comparaison. σ_Mack, lui, alimente AUSSI
    `sigma_total_compose = √(σ_Mack² + σ_modèle²)`, d'où sortent les percentiles
    PRINCIPAUX du rapport. Les retirer purement et simplement laisserait le
    livrable SANS AUCUNE mesure d'incertitude. `n4_best_estimate` traite donc
    les deux étages différemment : la colonne comparative disparaît, la mesure
    principale bascule sur le Bootstrap s'il est publiable, et sinon reste
    publiée avec sa provenance CONTESTÉE écrite noir sur blanc.
    """
    return not any(
        h.statut == NON_VALIDEE and PERCENTILES_MACK in (h.critique_pour or ())
        for h in hypotheses.values()
    )


def couvertures_par_annee(
    C:          np.ndarray,
    hypotheses: Dict[str, ResultatHypothese],
) -> Dict[str, Any]:
    """Traduit les verdicts par colonne / global en DEUX couvertures par année.

    RÈGLE DE PROPAGATION. Une année `i` projette à travers les colonnes
    `j = k_i … m−2`, où `k_i = min(n−i−1, m−1)` est sa dernière colonne connue.
    Elle est donc exposée à TOUTES les colonnes de son avenir :

        couverture_motif[i]      = pire des CLM-H2 sur j ∈ [k_i, m−2]
        couverture_volatilite[i] = pire de (CLM-H3 sur ces mêmes colonnes,
                                            CLM-H4 — global, la queue vaut
                                            pour toutes les années)

    Conséquence actuariellement juste : les années JEUNES sont exposées à tout
    le motif, les ANCIENNES à sa seule queue. L'année la plus ancienne d'un
    triangle carré ne traverse aucune colonne — son motif est validé sans objet,
    et seule la queue peut encore l'affecter.

    ⚠️ DEUX COUVERTURES SÉPARÉES, JAMAIS CONFONDUES. Le motif porte sur la
    RÉSERVE : il concerne les trois méthodes qui construisent le Best Estimate,
    puisqu'elles consomment toutes les mêmes facteurs. La volatilité porte sur
    ce que Mack publie AUTOUR de la réserve : un échec n'y touche pas le point
    estimate, seulement les percentiles.

    ⚠️ CE QUE CETTE FONCTION NE FAIT PAS. Elle DÉCRIT la couverture, elle
    n'exclut rien et ne pondère rien. Le second volet du filet de sécurité —
    « même Chain Ladder ne se calcule pas » — n'est pas décidable ici : il exige
    de connaître les réserves, qui n'existent qu'en N3. Il appartient au niveau
    qui les possède.
    """
    n, m = C.shape
    h2 = hypotheses.get('CLM-H2')
    h3 = hypotheses.get('CLM-H3')
    h4 = hypotheses.get('CLM-H4')

    par_colonne_h2 = {d['colonne']: d.get('statut', NON_TESTABLE)
                      for d in (h2.detail if h2 else ()) if 'colonne' in d}
    par_colonne_h3 = {d['colonne']: d.get('statut', NON_TESTABLE)
                      for d in (h3.detail if h3 else ()) if 'colonne' in d}
    statut_h4 = h4.statut if h4 else NON_TESTABLE

    annees: List[Dict[str, Any]] = []
    for i in range(n):
        k_i = min(n - i - 1, m - 1)
        traversees = list(range(k_i, m - 1))
        if traversees:
            motif = _pire_statut([par_colonne_h2.get(j, NON_TESTABLE)
                                  for j in traversees])
            vol_motif = _pire_statut([par_colonne_h3.get(j, NON_TESTABLE)
                                      for j in traversees])
        else:
            # Année entièrement développée : plus aucun facteur à traverser.
            motif, vol_motif = VALIDEE, VALIDEE
        volatilite = _pire_statut([vol_motif, statut_h4])
        annees.append({
            'annee':                 i,
            'derniere_colonne_connue': k_i,
            'colonnes_traversees':   traversees,
            'couverture_motif':      motif,
            'couverture_volatilite': volatilite,
            'filet_requis':          motif == NON_VALIDEE,
        })

    compte = lambda cle, val: sum(1 for a in annees if a[cle] == val)
    return {
        'annees': annees,
        'synthese': {
            'motif_non_validees':      compte('couverture_motif', NON_VALIDEE),
            'motif_a_justifier':       compte('couverture_motif', A_JUSTIFIER),
            'volatilite_non_validees': compte('couverture_volatilite', NON_VALIDEE),
            'volatilite_a_justifier':  compte('couverture_volatilite', A_JUSTIFIER),
            'annees_sous_filet':       [a['annee'] for a in annees if a['filet_requis']],
        },
    }


# =============================================================================
#  POINT D'ENTRÉE
# =============================================================================

def verifier_hypotheses_clm(
    C:          np.ndarray,
    *,
    tail_info:  Optional[Dict[str, Any]] = None,
    facteurs:   Optional[np.ndarray] = None,
    annee_base: int = 1,
) -> Dict[str, Any]:
    """Vérifie les quatre hypothèses et rend un rapport structuré.

    Chain Ladder est concerné par CLM-H1 et CLM-H2 ; Mack y ajoute CLM-H3 et,
    dès qu'une queue est appliquée, CLM-H4.

    RIEN N'EST DÉCIDÉ ICI. Aucune méthode n'est exclue, aucun poids modifié :
    ce module produit des verdicts, la gouvernance en tirera les conséquences.
    """
    h1 = clm_h1_effet_calendaire(C)
    h2 = clm_h2_existence_facteurs(C)
    h3 = clm_h3_structure_variance(C)
    h4 = clm_h4_incertitude_queue(C, tail_info=tail_info, facteurs=facteurs,
                                  annee_base=annee_base)
    resultats = {r.code: r for r in (h1, h2, h3, h4)}
    _pire = lambda codes: _pire_statut([resultats[c].statut for c in codes])

    return {
        'hypotheses':  {code: r.synthese() for code, r in resultats.items()},
        'couvertures': couvertures_par_annee(C, resultats),
        # Le PORTEUR de la cible `percentiles_mack`, calqué sur son
        # équivalent Bootstrap `percentiles_publiables`.
        'percentiles_mack_publiables': percentiles_mack_publiables(resultats),
        'chain_ladder': {'hypotheses': ['CLM-H1', 'CLM-H2'],
                         'statut_le_plus_severe': _pire(['CLM-H1', 'CLM-H2'])},
        'mack':         {'hypotheses': ['CLM-H1', 'CLM-H2', 'CLM-H3', 'CLM-H4'],
                         'statut_le_plus_severe': _pire(
                             ['CLM-H1', 'CLM-H2', 'CLM-H3', 'CLM-H4'])},
        'scipy_disponible': SCIPY_OK,
    }

# =============================================================================
#  LE DÉTAIL DE H1, COLONNE PAR COLONNE  (lot C3b — remplace le graphique g8)
# =============================================================================

def lignes_correlations_h1(n2):
    """Les corrélations de Spearman colonne par colonne, prêtes à afficher.

    ⚠️ CES LIGNES N'ATTEIGNAIENT AUCUN LIVRABLE AVANT LE LOT C3b. Elles ne
    vivaient que dans le graphique `g8_h1_independance` — cinq barres et une
    ligne de seuil. Une barre ne porte QUE la corrélation : ni le seuil, ni la
    significativité, ni le verdict de la colonne. g8 est retiré, ce tableau le
    remplace, et il porte les quatre.

    SOURCE UNIQUE, comme `lignes_hypotheses_bfcc` : l'Excel et le rapport HTML
    lisent la même fonction. Une colonne non testée ressort NON TESTABLE,
    jamais en valeur par défaut — c'est la règle du lot BFCC.
    """
    h1 = (n2 or {}).get('h1_independance') or {}
    seuil = float(h1.get('seuil_utilise', 0.50))
    lignes = []
    for i, d in enumerate(h1.get('details') or []):
        corr = d.get('corr')
        sig = bool(d.get('significatif', False))
        if corr is None:
            statut = 'NON TESTABLE'
        elif sig or abs(float(corr)) > seuil:
            statut = 'À JUSTIFIER'
        else:
            statut = 'VALIDÉE'
        lignes.append({
            'colonnes':     str(d.get('colonnes', 'Col %d' % i)),
            'corr':         None if corr is None else float(corr),
            'corr_abs':     None if corr is None else abs(float(corr)),
            'seuil':        seuil,
            'significatif': sig,
            'statut':       statut,
            'ok':           statut == 'VALIDÉE',
        })
    return lignes
