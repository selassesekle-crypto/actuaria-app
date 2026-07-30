# =============================================================================
#  ActuarIA — Agent A7 Ibrahim
#  n2_hypotheses.py  —  Niveau 2 : Validation des hypothèses H1/H2/H4
# =============================================================================
#
#  ⚠️ CE MODULE NE CALCULE PLUS AUCUN LOSS RATIO.
#  ─────────────────────────────────────────────
#  L'ancienne H3 « qualité de l'a priori BF » vivait ici et produisait un second
#  loss ratio, concurrent de celui de N3. Trois défauts mesurés l'ont fait
#  supprimer, pas déplacer :
#
#  · Elle divisait `C[i, dernière colonne connue]` par la prime — donc le PAYÉ À
#    DATE, pas l'ultime, contre la figure 14 du guide de l'Institut des Actuaires
#    qui rapporte la CHARGE ULTIME à la prime acquise. Biais systématiquement
#    baissier : −9,08 % sur GenIns, −4,39 % sur RAA.
#  · Son score valait `100 − CV×200`, c'est-à-dire la seule dispersion. Le
#    contrôle de plage était calculé dans `ok`… que la sélection ne lisait jamais.
#    Mesuré : un loss ratio de 364,7 % obtenait 81/100 et passait la gate.
#  · Sans primes, elle fabriquait un loss ratio par `C[i,0] / 0.30` — jumeau du
#    proxy `/0.35` supprimé de N3 au lot précédent, avec une constante inventée
#    DIFFÉRENTE. Sur GenIns, il publiait « LR = 398,9 % » dans le rapport pendant
#    que Bornhuetter-Ferguson y annonçait « non calculée ».
#
#  Le loss ratio a désormais UN SEUL propriétaire, N3, et c'est celui-là que
#  BFCC-H4 juge (`n2_hypotheses_bfcc`). `scores_confiance` disparaît avec lui :
#  après le lot B il n'alimentait plus que BF et Cape Cod, depuis cette seule H3.
#
#  Corrections v5.0 vs v4.0 :
#    · Bug methode_cl_retenue corrigé : valider() expose maintenant
#      'methode_cl_retenue' directement dans le dict retourné,
#      calculée via _choisir_variante_cl() cohérente avec methode_recommandee
#    · Seuils H2 dynamiques depuis lob_config (plus de 15% codé en dur)
#    · _choisir_variante_cl() séparée et documentée (5 cas + fallback)
#
#  Références :
#    · Mack (1993) — ASTIN Bulletin 23(2) : hypothèses H1-H3
#    · England & Verrall (2002) : H4 homoscédasticité Bootstrap ODP
#    · Spearman (1904) : test de rang pour H1
#
# =============================================================================

import logging
from typing import Dict, Any, List, Tuple

import numpy as np

from .config.lob_config import get_lob_config
# Reconstruction des facteurs individuels : SOURCE UNIQUE. Les trois boucles
# identiques qui vivaient ici (H1, H2, H4) ont été remplacées par cet appel.
from .n2_hypotheses_clm import facteurs_individuels

logger = logging.getLogger('actuaria.a7')


class HypothesesValidator:
    """
    Valide les hypothèses actuarielles AVANT tout calcul de méthode.

    H1 — Corrélation entre facteurs de développement consécutifs
         Test de Spearman sur les facteurs individuels entre colonnes
         consécutives. Si corrélation significative → CL et Mack biaisés.
         ⚠️ NE TESTE PAS l'indépendance des années de survenance, contrairement
         à ce que son ancien libellé affirmait : une corrélation entre facteurs
         de colonnes voisines ne dit rien d'un effet propre à une année de
         survenance ou à une année calendaire. Ce contrôle-là est CLM-H1
         (`n2_hypotheses_clm`), qui applique le test des signes par diagonale
         de l'annexe 9.d du guide IA 2023.

    H2 — Stabilité des facteurs dans le temps
         CV des facteurs par colonne et dérive temporelle (anciens vs récents).
         Seuils paramétrés par LoB (depuis lob_config).

    H4 — Homoscédasticité (England & Verrall 2002)
         Variance des résidus pondérés homogène entre colonnes.
         Condition nécessaire pour la validité du Bootstrap ODP.

    Correction critique v5.0
    ------------------------
    La méthode valider() retourne maintenant 'methode_cl_retenue' dans son
    dict, calculée par _choisir_variante_cl(). Cela garantit la cohérence
    entre la recommandation N2 et le choix de variante CL en N3/N4.
    """

    def __init__(self):
        pass

    # =========================================================================
    #  POINT D'ENTRÉE UNIQUE
    # =========================================================================

    def valider(
        self,
        C:         np.ndarray,
        lob:       str = 'generique',
    ) -> Dict[str, Any]:
        """
        Lance les tests H1, H2 et H4 et retourne un rapport structuré.

        Parameters
        ----------
        C : np.ndarray
            Triangle cumulé (n × m).
        lob : str
            Ligne d'activité — pilote les seuils H2 depuis lob_config.
            Défaut : 'generique' (seuils standards CV=15%, dérive=20%).

        Les paramètres `primes` et `lr_manuel` ont disparu : ils ne servaient
        qu'à l'ancienne H3, qui calculait ici un second loss ratio concurrent de
        celui de N3 (cf. en-tête du module). N2 n'a plus besoin de l'exposition.

        Returns
        -------
        dict avec :
            h1_independance, h2_stabilite, h4_homosc_bootstrap
            methode_recommandee     : str  — méthode principale conseillée
            methode_cl_retenue      : str  — variante CL à utiliser en N3
                                      ('standard'|'mediane'|'trimmed_mean'|
                                       'volume_weighted')
            raison_recommandation   : str
            raison_cl               : str  — justification du choix CL
            statut_global           : 'VERT'|'AMBRE'|'ROUGE'
            alertes, infos          : list[str]
        """
        n, m    = C.shape
        alertes: List[str] = []
        infos:   List[str] = []

        # Récupérer la config LoB (seuils H2 adaptés)
        cfg_lob = get_lob_config(lob)

        # ── H1 : Indépendance ────────────────────────────────────────────────
        h1 = self._tester_h1_independance(C, alertes, infos, cfg_lob)

        # ── H2 : Stabilité (seuils depuis lob_config) ────────────────────────
        h2 = self._tester_h2_stabilite(C, alertes, infos, cfg_lob)

        # ── H4 : Homoscédasticité ─────────────────────────────────────────────
        h4 = self._tester_h4_homosc(C, alertes, infos)

        # ── Méthode recommandée ───────────────────────────────────────────────
        methode_rec, raison_rec = self._recommander_methode(h1, h2, n)

        # ── Variante CL : RECOMMANDÉE, plus imposée (lot B) ────────────────────
        # La réserve se calcule désormais sur l'estimateur STANDARD par défaut —
        # celui pour lequel les hypothèses sont testées (CLM) et pour lequel la
        # volatilité de Mack est définie. La recommandation reste calculée et
        # exposée ; l'activer est une décision d'actuaire, via `methode_cl`.
        variante_recommandee, raison_cl = self._choisir_variante_cl(h1, h2)
        methode_cl = 'standard'

        # ── Alertes spécifiques à la LoB ──────────────────────────────────────
        for alerte_lob in cfg_lob.get('alertes_specifiques', []):
            infos.append(f"ℹ️ [{cfg_lob['label']}] {alerte_lob}")

        # ── Statut global ─────────────────────────────────────────────────────
        if not h1['ok'] and not h2['ok']:
            statut = 'ROUGE'
        elif not h1['ok'] or not h2['ok']:
            statut = 'AMBRE'
        else:
            statut = 'VERT'

        if self.verbose_log:
            logger.info(
                f"N2 — statut={statut} | methode_rec={methode_rec} | "
                f"methode_cl={methode_cl}"
            )

        return {
            'h1_independance':       h1,
            'h2_stabilite':          h2,
            'h4_homosc_bootstrap':   h4,
            'methode_recommandee':   methode_rec,
            # Toujours 'standard' sauf choix explicite de l'actuaire en amont :
            # la réserve se calcule sur l'estimateur de Mack (cf. lot B).
            'methode_cl_retenue':      methode_cl,
            # La bascule que le système AURAIT faite automatiquement avant le
            # lot B — exposée pour que l'actuaire puisse la retenir en connaissance
            # de cause, jamais appliquée d'office.
            'variante_cl_recommandee': variante_recommandee,
            'raison_recommandation': raison_rec,
            'raison_cl':             raison_cl,
            'statut_global':         statut,
            'alertes':               alertes,
            'infos':                 infos,
            'lob':                   lob,
            'lob_label':             cfg_lob['label'],
        }

    @property
    def verbose_log(self) -> bool:
        """Log niveau INFO si logger actuaria.a7 actif."""
        return logger.isEnabledFor(logging.INFO)

    # =========================================================================
    #  H1 : CORRÉLATION ENTRE FACTEURS DE DÉVELOPPEMENT CONSÉCUTIFS
    # =========================================================================

    def _tester_h1_independance(
        self,
        C:        np.ndarray,
        alertes:  List,
        infos:    List,
        cfg_lob:  Dict,
    ) -> Dict:
        """
        Corrélation entre facteurs de développement consécutifs.

        Principe : pour chaque paire de colonnes consécutives (j, j+1),
        calculer la corrélation de Spearman entre les vecteurs de facteurs
        individuels f[i,j] = C[i,j+1]/C[i,j].

        ⚠️ CE QUE CE TEST NE FAIT PAS. Il s'intitulait « indépendance des années
        de survenance » et affirmait qu'une corrélation révélait « des années de
        survenance au comportement systématiquement différent » : c'est faux. Une
        corrélation entre facteurs de colonnes voisines mesure la dépendance
        sérielle du DÉVELOPPEMENT, pas un effet propre à une année. Le contrôle
        d'indépendance des années — test des signes par diagonale de l'annexe 9.d
        du guide IA 2023 — est CLM-H1, dans `n2_hypotheses_clm`.

        Le nom de la clé de sortie (`h1_independance`) est conservé : il est lu
        par n4 et les livrables, et le renommer déborderait du périmètre.

        Seuil d'alerte : |corr_moy| > h1_seuil_corr (depuis lob_config).
        H1 rejetée si : corr_moy > seuil ET au moins 2 colonnes significatives
                        (pval < 0.05 et |corr| > seuil).
        """
        try:
            from scipy.stats import spearmanr
        except ImportError:
            return {
                'ok': True, 'score': 70,
                'corr_max': 0, 'corr_moy': 0,
                'n_colonnes_testees': 0, 'n_colonnes_sig': 0,
                'message': "H1 non testable — scipy non disponible",
                'details': [],
            }

        n, m     = C.shape
        seuil    = cfg_lob.get('h1_seuil_corr', 0.50)
        corrs    = []
        details  = []

        # Facteurs reconstruits par la SOURCE UNIQUE (n2_hypotheses_clm), plus
        # par une boucle locale : cf. `facteurs_individuels`.
        colonnes = facteurs_individuels(C)

        for j in range(m - 2):
            # Appariement sur l'année i : une paire n'existe que si les trois
            # cellules C[i,j], C[i,j+1], C[i,j+2] sont exploitables — c'est
            # exactement l'intersection des deux colonnes de facteurs.
            suivants = {i: f for i, f, _ in colonnes[j + 1]}
            f_j  = [f for i, f, _ in colonnes[j] if i in suivants]
            f_j1 = [suivants[i] for i, _, _ in colonnes[j] if i in suivants]

            if len(f_j) >= 4:
                corr, pval = spearmanr(f_j, f_j1)
                if not np.isnan(corr):
                    corrs.append(abs(corr))
                    details.append({
                        'colonnes':    f"j={j}→j+1={j+1}",
                        'corr':        round(float(corr), 3),
                        'pval':        round(float(pval), 3),
                        'n_obs':       len(f_j),
                        'significatif': pval < 0.05 and abs(corr) > seuil,
                    })

        if not corrs:
            return {
                'ok': True, 'score': 80,
                'corr_max': 0, 'corr_moy': 0,
                'n_colonnes_testees': 0, 'n_colonnes_sig': 0,
                'message': "H1 non testable — trop peu de données (< 4 obs par colonne)",
                'details': [],
            }

        corr_moy = float(np.mean(corrs))
        corr_max = float(np.max(corrs))
        n_sig    = sum(1 for d in details if d['significatif'])

        ok    = corr_moy < seuil and n_sig <= 2
        score = max(0, int((1 - corr_moy) * 100))

        if not ok:
            alertes.append(
                f"⚠️ H1 Indépendance : corrélation Spearman moyenne = {corr_moy:.2f} "
                f"(seuil LoB = {seuil:.2f}), {n_sig} colonne(s) significative(s). "
                f"Années de survenance dépendantes → BF ou Cape Cod recommandés."
            )
            message = (
                f"H1 REJETÉE — corrélation Spearman moy={corr_moy:.2f}, "
                f"max={corr_max:.2f}. {n_sig} paire(s) de colonnes montrent "
                f"une dépendance significative. CL et Mack potentiellement biaisés."
            )
        else:
            if corr_moy > seuil * 0.6:
                alertes.append(
                    f"🟡 H1 Indépendance : corrélation moy={corr_moy:.2f} "
                    f"— proche du seuil ({seuil:.2f}), surveiller."
                )
            infos.append(f"✅ H1 Indépendance validée (corr_moy={corr_moy:.2f})")
            message = (
                f"H1 VALIDÉE — corrélation Spearman moy={corr_moy:.2f} < {seuil:.2f}. "
                f"Les années de survenance sont indépendantes. CL est approprié."
            )

        return {
            'ok':                   ok,
            'score':                score,
            'corr_max':             round(corr_max, 3),
            'corr_moy':             round(corr_moy, 3),
            'n_colonnes_testees':   len(corrs),
            'n_colonnes_sig':       n_sig,
            'seuil_utilise':        seuil,
            'message':              message,
            'details':              details[:5],
        }

    # =========================================================================
    #  H2 : STABILITÉ DES FACTEURS DANS LE TEMPS
    # =========================================================================

    def _tester_h2_stabilite(
        self,
        C:       np.ndarray,
        alertes: List,
        infos:   List,
        cfg_lob: Dict,
    ) -> Dict:
        """
        Stabilité des facteurs de développement dans le temps.

        Deux sous-tests :

        Test 2a — CV des facteurs par colonne
            Pour chaque colonne j, calculer le coefficient de variation
            CV_j = σ(f[·,j]) / μ(f[·,j]).
            Si CV_moy > seuil_cv (depuis lob_config) → instabilité.

        Test 2b — Dérive temporelle
            Pour chaque colonne j, comparer la moyenne des facteurs sur
            la première moitié des années (anciennes) vs la deuxième
            moitié (récentes).
            Si |f_recent - f_ancien| / f_ancien > seuil_derive → dérive.

        Note : seuils paramétrés par LoB (plus stricts en MRH, plus larges
        en RC Médicale) — cf. config/lob_config.py.
        """
        n, m         = C.shape
        seuil_cv     = cfg_lob.get('h2_seuil_cv',     0.15)
        seuil_derive = cfg_lob.get('h2_seuil_derive',  0.20)
        cv_cols      = []
        derive_cols  = []
        details      = []

        colonnes = facteurs_individuels(C)          # source unique

        for j in range(m - 1):
            facteurs = [f for _, f, _ in colonnes[j]]

            if len(facteurs) >= 3:
                arr = np.array(facteurs)
                moy = float(np.mean(arr))
                std = float(np.std(arr, ddof=1))
                cv  = std / moy if moy > 0 else 0.0
                cv_cols.append(cv)

                derive = 0.0
                mid    = len(facteurs) // 2
                if mid >= 2:
                    m_anc   = float(np.mean(arr[:mid]))
                    m_rec   = float(np.mean(arr[mid:]))
                    derive  = abs(m_rec - m_anc) / max(m_anc, 1e-9)
                    derive_cols.append(derive)

                details.append({
                    'colonne': j,
                    'n_obs':   len(facteurs),
                    'f_moyen': round(moy, 4),
                    'cv':      round(cv,  3),
                    'derive':  round(derive, 3),
                })

        if not cv_cols:
            return {
                'ok': True, 'score': 80,
                'cv_moy': 0, 'cv_max': 0, 'derive_moy': 0,
                'ok_cv': True, 'ok_derive': True,
                'message': "H2 non testable — trop peu de données",
                'details': [],
            }

        cv_moy     = float(np.mean(cv_cols))
        cv_max     = float(np.max(cv_cols))
        derive_moy = float(np.mean(derive_cols)) if derive_cols else 0.0

        ok_cv     = cv_moy    < seuil_cv
        ok_derive = derive_moy < seuil_derive
        ok        = ok_cv and ok_derive

        score = max(0, int((1 - cv_moy / max(seuil_cv * 2, 0.30)) * 100))

        if not ok_cv:
            alertes.append(
                f"⚠️ H2 Stabilité : CV moyen des facteurs = {cv_moy:.1%} "
                f"(seuil {cfg_lob['label']} = {seuil_cv:.0%}) "
                f"→ facteurs instables. Variante médiane ou trimmed_mean recommandée."
            )
        if not ok_derive:
            alertes.append(
                f"⚠️ H2 Dérive temporelle : {derive_moy:.1%} entre facteurs "
                f"anciens et récents (seuil = {seuil_derive:.0%}) "
                f"→ triangle en évolution. Variante volume_weighted recommandée."
            )
        if ok:
            infos.append(
                f"✅ H2 Stabilité validée — CV={cv_moy:.1%} < {seuil_cv:.0%}, "
                f"dérive={derive_moy:.1%} < {seuil_derive:.0%}"
            )

        message = (
            f"H2 {'VALIDÉE' if ok else 'REJETÉE'} — "
            f"CV moy={cv_moy:.1%} (seuil {seuil_cv:.0%}), "
            f"dérive={derive_moy:.1%} (seuil {seuil_derive:.0%}). "
            + (
                "Les facteurs sont stables dans le temps."
                if ok else
                "Les facteurs montrent une instabilité ou une dérive temporelle."
            )
        )

        return {
            'ok':          ok,
            'ok_cv':       ok_cv,
            'ok_derive':   ok_derive,
            'score':       score,
            'cv_moy':      round(cv_moy,     4),
            'cv_max':      round(cv_max,     4),
            'derive_moy':  round(derive_moy, 4),
            'seuil_cv':    seuil_cv,
            'seuil_derive': seuil_derive,
            'message':     message,
            'details':     details,
        }

    # =========================================================================
    #  H4 : HOMOSCÉDASTICITÉ (Bootstrap ODP)
    # =========================================================================

    def _tester_h4_homosc(
        self,
        C:       np.ndarray,
        alertes: List,
        infos:   List,
    ) -> Dict:
        """
        Homoscédasticité des résidus — condition du Bootstrap ODP.

        Référence : England & Verrall (2002), Insurance: Mathematics and Economics.

        Principe : tester si la variance des résidus pondérés est homogène
        entre colonnes. Pour chaque colonne j, calculer la variance pondérée :

            Var_j = Σ_i w_ij × (f_ij - f̄_j)²  /  Σ_i w_ij
            avec w_ij = C[i,j] (pondération volume)

        Si CV(Var_j) < 1.0 : homoscédasticité acceptable.

        Le facteur de sur-dispersion φ est la moyenne de Var_j — il est
        utilisé par le Bootstrap ODP pour calibrer les résidus de Pearson.
        """
        n, m            = C.shape
        var_cols: List  = []

        colonnes = facteurs_individuels(C)          # source unique

        for j in range(m - 1):
            facteurs = [f for _, f, _ in colonnes[j]]
            poids    = [c for _, _, c in colonnes[j]]

            if len(facteurs) >= 3:
                arr  = np.array(facteurs)
                w    = np.array(poids)
                moy  = np.average(arr, weights=w)
                var  = np.average((arr - moy) ** 2, weights=w)
                var_cols.append(float(var))

        if len(var_cols) < 3:
            return {
                'ok':     True,
                'score':  75,
                'phi':    0.0,
                'cv_var': 0.0,
                'message': "H4 non testable — moins de 3 colonnes disponibles",
            }

        var_arr = np.array(var_cols)
        cv_var  = float(np.std(var_arr) / max(np.mean(var_arr), 1e-12))
        phi     = float(np.mean(var_arr))

        ok    = cv_var < 1.0
        score = max(0, int((1 - cv_var / 2.0) * 100))

        if not ok:
            alertes.append(
                f"🟡 H4 Homoscédasticité : CV variances = {cv_var:.2f} > 1.0 "
                f"→ Bootstrap ODP moins fiable. "
                f"Interpréter les percentiles P90/P99.5 avec prudence."
            )
            message = (
                f"H4 HÉTÉROSCÉDASTICITÉ détectée — CV variances = {cv_var:.2f}. "
                f"La variance des résidus n'est pas stable entre colonnes. "
                f"Bootstrap ODP fournit des intervalles approximatifs."
            )
        else:
            infos.append(f"✅ H4 Homoscédasticité validée (CV var={cv_var:.2f}, φ={phi:.6f})")
            message = (
                f"H4 VALIDÉE — CV variances = {cv_var:.2f} < 1.0, "
                f"φ={phi:.6f}. Bootstrap ODP fiable."
            )

        return {
            'ok':     ok,
            'score':  score,
            'phi':    round(phi,    6),
            'cv_var': round(cv_var, 3),
            'message': message,
        }

    # =========================================================================
    #  MÉTHODE RECOMMANDÉE
    # =========================================================================

    def _recommander_methode(
        self,
        h1:      Dict,
        h2:      Dict,
        n:       int,
    ) -> Tuple[str, str]:
        """
        Recommande la méthode principale avec justification explicite.

        ⚠️ PUREMENT INFORMATIF DEPUIS LE LOT B. Cette recommandation ne force
        plus l'inclusion d'une méthode dans le Best Estimate et ne lui accorde
        plus de poids minimum : la sélection se décide sur la couverture du
        motif, année par année, et les méthodes admises sont pondérées à égalité.
        Elle reste affichée comme un avis de lecture du triangle.

        Règles de décision (par ordre de priorité) :
        1. Triangle trop petit (n < 5) → Cape Cod
        2. H1 + H2 validées → Chain Ladder
        3. H1 rejetée → Bornhuetter-Ferguson
        4. H2 rejetée seule → Bornhuetter-Ferguson
        5. Fallback → Chain Ladder (INATTEIGNABLE par construction : R2-R4
           couvrent toutes les combinaisons H1×H2)

        LES DEUX ANCIENNES RÈGLES « H1 rejetée » SONT FUSIONNÉES. Elles
        arbitraient entre Bornhuetter-Ferguson et Cape Cod sur le score de
        l'ancienne H3, supprimée avec le loss ratio de N2. Reconstruire cet
        arbitrage ici est impossible ET indésirable : impossible parce que le
        loss ratio n'existe qu'après N3, indésirable parce que ce qui départage
        réellement les deux méthodes — la provenance de l'a priori et la
        stabilité du loss ratio — est désormais l'objet de BFCC-H4 et BFCC-H5,
        avec un verdict motivé plutôt qu'un score. La recommandation dit donc ce
        qu'elle sait : l'a priori exogène vaut mieux ici que le seul triangle.

        La règle 2 arbitrait auparavant entre « Mack 1993 » et Chain Ladder sur
        un score de méthode. Deux raisons de ne plus le faire : ce score a
        disparu (il reposait sur les anciennes H1/H2/H4), et surtout le point
        estimate de Mack EST celui de Chain Ladder — les présenter comme deux
        recommandations distinctes n'avait pas de sens.
        """
        # Règle 1 : trop peu de données
        if n < 5:
            return 'cape_cod', (
                f"Triangle de petite taille ({n} années) — Cape Cod recommandé : "
                f"il exploite un a priori externe quand les données sont rares."
            )

        # Règle 2 : H1 + H2 validées
        if h1['ok'] and h2['ok']:
            return 'chain_ladder', (
                "H1 et H2 validées → Chain Ladder retenu : les facteurs de "
                "développement sont exploitables tels quels. Mack 1993 en fournit "
                "la volatilité, son estimation centrale étant identique."
            )

        # Règle 3 : H1 rejetée
        if not h1['ok']:
            return 'bornhuetter_ferguson', (
                f"H1 REJETÉE (corr_moy={h1['corr_moy']:.2f}) → CL biaisé. "
                f"Bornhuetter-Ferguson recommandé : ancrage sur un a priori "
                f"extérieur aux corrélations du triangle. Sa recevabilité — "
                f"provenance de l'a priori, stabilité du loss ratio — est jugée "
                f"par BFCC-H4 et BFCC-H5, après N3."
            )

        # Règle 4 : H2 rejetée seule
        if not h2['ok']:
            return 'bornhuetter_ferguson', (
                f"H2 REJETÉE (CV={h2['cv_moy']:.1%}, dérive={h2['derive_moy']:.1%}) "
                f"→ facteurs instables, CL sensible aux outliers. "
                f"Bornhuetter-Ferguson recommandé pour sa robustesse."
            )

        # Règle 5 : fallback terminal — INATTEIGNABLE par construction. R2-R4
        # couvrent toutes les combinaisons H1×H2 (H1∧H2→R2 ; ¬H1→R3 ; ¬H2→R4).
        # Défaut SÛR = chain_ladder (jamais 'bootstrap_odp' via max(scores), que N4
        # ne sait pas pondérer dans le BE).
        return 'chain_ladder', (
            "Fallback sécurisé (inatteignable par construction) — Chain Ladder par défaut."
        )

    # =========================================================================
    #  VARIANTE CL RETENUE (CORRECTION BUG v4.0)
    # =========================================================================

    def _choisir_variante_cl(
        self,
        h1:  Dict,
        h2:  Dict,
    ) -> Tuple[str, str]:
        """
        Choisit la variante de Chain Ladder à utiliser en N3.

        CORRECTION DU BUG v4.0
        ----------------------
        En v4.0, cette logique était dupliquée dans AgentA7Provisionnement
        sous le nom _choisir_methode_cl(), et n'utilisait pas les résultats
        de N2 correctement (la clé 'methode_cl_retenue' n'était jamais
        présente dans le dict retourné par valider()).

        En v5.0 : calculé ici, exposé dans le dict retourné par valider(),
        utilisé directement dans agent.py. Source unique de vérité.

        ⚠️ CETTE FONCTION NE DÉCIDE PLUS — ELLE RECOMMANDE.
        --------------------------------------------------
        Jusqu'au lot B, sa sortie pilotait directement le calcul de la réserve :
        un CV élevé faisait basculer TOUTES les colonnes sur un autre estimateur,
        automatiquement et en silence. Trois raisons de ne plus le faire :

        · Le déclencheur est un SYMPTÔME, pas un diagnostic. Mesuré sur le
          triangle RAA : `cv_moy` = 31,5 % vient d'UNE colonne à 150 %, elle-même
          due à UNE cellule (C[1,0] = 106 contre 1 000-5 700 ailleurs) qui produit
          un facteur de 40,4 face à une médiane de 4,26. La bonne réponse est
          d'examiner ce point, pas de changer d'estimateur partout.
        · Le remède était GLOBAL pour un problème LOCAL : la bascule touchait
          aussi les colonnes à CV de 5 %, où l'estimateur de Mack est optimal.
        · Elle rompait EN SILENCE le lien avec la théorie : σ, la MSEP et les
          percentiles de Mack sont dérivés POUR l'estimateur pondéré volume.
          Conséquence mesurée : l'oracle RAA d'A7 valait 54 059 / 27 022, quand
          Mack et le guide publient 52 135 / 26 909.

        Désormais la recommandation est EXPOSÉE (`variante_cl_recommandee`), et
        le choix appartient à l'actuaire via le paramètre `methode_cl` de run(),
        informé par le diagnostic CLM colonne par colonne.

        Variantes disponibles
        ---------------------
        'standard'        : facteur pondéré volume — estimateur de Mack (1993).
                            f_j = Σ C[i,j+1] / Σ C[i,j]
        'volume_weighted' : ⚠️ PAS un alias de standard, contrairement à ce que
                            cette docstring affirmait. Il pondère par √C[i,j] et
                            non par C[i,j]. Mesuré sur RAA : f₀ = 4,347 contre
                            2,999, réserve 63 500 contre 52 135, soit +22 %.
        'mediane'         : médiane des facteurs individuels par colonne.
                            Robuste aux outliers, insensible au volume.
                            Préféré si CV > seuil élevé.
        'trimmed_mean'    : moyenne écrêtée (10% haut, 10% bas) par colonne.
                            Compromis entre standard et médiane.
                            Préféré si CV modéré (10–20%).

        Règles de décision (5 cas + fallback)
        --------------------------------------
        Cas 1 : H1 + H2 OK                         → standard
        Cas 2 : H2 rejetée sur dérive > 20%         → volume_weighted
        Cas 3 : H2 rejetée sur CV > 20%             → mediane
        Cas 4 : H2 rejetée sur CV 10–20%            → trimmed_mean
        Cas 5 : H1 rejetée seule (H2 OK)            → volume_weighted
        Fallback                                     → standard
        """
        h1_ok    = h1.get('ok', True)
        h2_ok    = h2.get('ok', True)
        cv       = h2.get('cv_moy',    0.0)
        derive   = h2.get('derive_moy', 0.0)
        seuil_cv = h2.get('seuil_cv',   0.15)

        # Cas 1 : tout validé
        if h1_ok and h2_ok:
            return 'standard', (
                "H1 et H2 validées → variante standard (pondération volume). "
                "Estimateur optimal de Mack (1993)."
            )

        # Cas 2 : dérive temporelle dominante
        if not h2_ok and derive > 0.20 and cv <= 0.20:
            return 'volume_weighted', (
                f"H2 rejetée sur dérive temporelle ({derive:.1%} > 20%). "
                f"volume_weighted pondère par C[i,j] → favorise les années "
                f"récentes (volumes généralement plus élevés)."
            )

        # Cas 3 : forte dispersion
        if not h2_ok and cv > 0.20:
            return 'mediane', (
                f"H2 rejetée sur forte dispersion (CV={cv:.1%} > 20%). "
                f"Médiane : insensible aux facteurs extrêmes, "
                f"robuste sur portefeuilles hétérogènes."
            )

        # Cas 4 : dispersion modérée
        if not h2_ok and cv > seuil_cv:
            return 'trimmed_mean', (
                f"H2 rejetée sur dispersion modérée (CV={cv:.1%}, "
                f"seuil LoB={seuil_cv:.0%}). "
                f"trimmed_mean écrête les 10% extrêmes sans aller jusqu'à la médiane."
            )

        # Cas 5 : H1 rejetée seule
        if not h1_ok:
            return 'volume_weighted', (
                f"H1 rejetée (corr={h1.get('corr_moy', 0):.2f}) — "
                f"BF/Cape Cod seront les méthodes principales (N4). "
                f"volume_weighted pour le CL utilisé en entrée de BF."
            )

        # Fallback sécurisé
        logger.warning(
            f"_choisir_variante_cl : cas non couvert "
            f"(h1={h1_ok}, h2={h2_ok}, cv={cv:.2f}, derive={derive:.2f}) "
            f"→ fallback standard"
        )
        return 'standard', "Fallback sécurisé — standard appliqué par défaut."
